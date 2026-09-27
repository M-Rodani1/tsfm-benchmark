"""Data cleaning with a complete audit trail.

Every change (and every flag that does not change data) becomes one row in the
cleaning report: ``ticker, date, issue, action, detail``. The rules are fixed in
``docs/PREREGISTRATION.md`` section 2; they are applied in this order:

1. ``weekend_row``      rows dated Saturday/Sunday                      -> dropped
2. ``duplicate_date``   repeated dates                                  -> keep last
3. ``nonpositive_price`` any of O/H/L/C/adj_close <= 0 or missing      -> dropped
4. ``stale_row``        volume == 0 and O == H == L == C               -> dropped
5. ``ohlc_violation``   H < max(O,C,L) or L > min(O,C,H)                -> H,L repaired
6. ``zero_volume``      volume == 0 (row kept)                          -> volume set NaN
7. ``suspect_split``    |ln adj_close_t/adj_close_{t-1}| > threshold    -> flagged only
8. ``missing_day``      a union-calendar day inside the asset's life    -> flagged only
   is absent (computed by :func:`flag_missing_days` after all assets are cleaned)

No winsorising, no outlier removal, no imputation of prices.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

PRICE_COLS = ["open", "high", "low", "close", "adj_close"]


@dataclass
class CleaningReport:
    rows: list[dict] = field(default_factory=list)

    def add(self, ticker: str, date: pd.Timestamp | None, issue: str, action: str, detail: str = "") -> None:
        self.rows.append(
            {
                "ticker": ticker,
                "date": pd.Timestamp(date) if date is not None else pd.NaT,
                "issue": issue,
                "action": action,
                "detail": detail,
            }
        )

    def extend(self, other: CleaningReport) -> None:
        self.rows.extend(other.rows)

    def to_frame(self) -> pd.DataFrame:
        cols = ["ticker", "date", "issue", "action", "detail"]
        if not self.rows:
            return pd.DataFrame(columns=cols)
        return pd.DataFrame(self.rows, columns=cols).sort_values(["ticker", "date", "issue"], kind="stable").reset_index(drop=True)

    def summary(self) -> pd.DataFrame:
        f = self.to_frame()
        if f.empty:
            return pd.DataFrame(columns=["ticker", "issue", "action", "count"])
        return f.groupby(["ticker", "issue", "action"]).size().rename("count").reset_index()


def clean_ohlcv(raw: pd.DataFrame, ticker: str, split_threshold: float = 0.35) -> tuple[pd.DataFrame, CleaningReport]:
    """Apply rules 1-7 to one ticker's raw frame. Returns (clean frame, report)."""
    rep = CleaningReport()
    df = raw.copy().sort_index(kind="stable")

    # 1. weekend rows
    wk = df.index.dayofweek >= 5
    for d in df.index[wk]:
        rep.add(ticker, d, "weekend_row", "dropped")
    df = df.loc[~wk]

    # 2. duplicates (keep last occurrence)
    dup = df.index.duplicated(keep="last")
    for d in df.index[dup]:
        rep.add(ticker, d, "duplicate_date", "dropped_earlier_copy")
    df = df.loc[~dup]

    # 3. non-positive or missing prices
    bad = (df[PRICE_COLS] <= 0).any(axis=1) | df[PRICE_COLS].isna().any(axis=1)
    for d in df.index[bad]:
        rep.add(ticker, d, "nonpositive_price", "dropped", _fmt_row(df.loc[d]))
    df = df.loc[~bad]

    # 4. stale rows: no trading and a flat price
    flat = (df["open"] == df["high"]) & (df["high"] == df["low"]) & (df["low"] == df["close"])
    stale = flat & (df["volume"].fillna(0) == 0)
    for d in df.index[stale]:
        rep.add(ticker, d, "stale_row", "dropped", _fmt_row(df.loc[d]))
    df = df.loc[~stale].copy()

    # 5. OHLC ordering
    hi_needed = df[["open", "high", "low", "close"]].max(axis=1)
    lo_needed = df[["open", "high", "low", "close"]].min(axis=1)
    viol = (df["high"] < hi_needed) | (df["low"] > lo_needed)
    for d in df.index[viol]:
        before = _fmt_row(df.loc[d])
        df.loc[d, "high"] = hi_needed.loc[d]
        df.loc[d, "low"] = lo_needed.loc[d]
        rep.add(ticker, d, "ohlc_violation", "repaired_high_low", f"before: {before}")

    # 6. zero volume on a trading row
    zv = df["volume"] == 0
    for d in df.index[zv]:
        rep.add(ticker, d, "zero_volume", "volume_set_missing")
    df.loc[zv, "volume"] = np.nan

    # 7. suspect split (flag only)
    lr = np.log(df["adj_close"]).diff()
    sus = lr.abs() > split_threshold
    for d in df.index[sus.fillna(False)]:
        rep.add(ticker, d, "suspect_split", "flagged_only", f"log return {lr.loc[d]:+.3f}")

    df.index.name = "date"
    return df, rep


def flag_missing_days(frames: dict[str, pd.DataFrame]) -> tuple[pd.DatetimeIndex, CleaningReport]:
    """Union trading calendar and rule 8 (days missing inside each asset's life)."""
    rep = CleaningReport()
    cal = pd.DatetimeIndex(sorted(set().union(*[set(f.index) for f in frames.values()]))) if frames else pd.DatetimeIndex([])
    for t, f in frames.items():
        if f.empty:
            continue
        life = cal[(cal >= f.index.min()) & (cal <= f.index.max())]
        for d in life.difference(f.index):
            rep.add(t, d, "missing_day", "flagged_only", "absent vs union calendar")
    return cal, rep


def _fmt_row(row: pd.Series) -> str:
    return ", ".join(f"{k}={row[k]:.6g}" for k in ("open", "high", "low", "close", "volume") if k in row)
