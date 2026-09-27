"""Data providers behind one interface.

A :class:`DataProvider` returns *raw* daily OHLCV for one ticker in a standard shape:

    index: DatetimeIndex (tz-naive, normalised to midnight, name "date")
    columns: open, high, low, close, adj_close, volume, dividends, splits

"Raw" means: exactly what the source delivered, with column names standardised and
nothing else changed. All cleaning happens later in :mod:`tsfm_rc.data.cleaning`, where
every change is logged.

Providers
---------
- :class:`YFinanceProvider` — Yahoo Finance through ``yfinance`` (network).
- :class:`CSVDirectoryProvider` — one ``<TICKER>.csv`` per ticker in Yahoo's export
  format (useful if ``yfinance`` breaks: download the CSVs by hand).
- :class:`FixtureProvider` — the committed synthetic fixtures (offline, tests/smoke).
"""

from __future__ import annotations

import abc
import datetime as dt
import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

STANDARD_COLUMNS = ["open", "high", "low", "close", "adj_close", "volume", "dividends", "splits"]

_RENAME = {
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "adj close": "adj_close",
    "adj_close": "adj_close",
    "adjclose": "adj_close",
    "volume": "volume",
    "dividends": "dividends",
    "stock splits": "splits",
    "stock_splits": "splits",
    "splits": "splits",
}


class ProviderError(RuntimeError):
    """The provider could not deliver data (network, unknown ticker, bad file)."""


def standardise(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Rename columns to the standard set and normalise the index. No value changes."""
    if df is None or len(df) == 0:
        raise ProviderError(f"{ticker}: provider returned no rows")
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):  # yf.download style (field, ticker)
        out.columns = [c[0] for c in out.columns]
    out.columns = [_RENAME.get(str(c).strip().lower(), str(c).strip().lower()) for c in out.columns]
    if "date" in out.columns:
        out = out.set_index("date")
    idx = pd.DatetimeIndex(pd.to_datetime(out.index))
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    out.index = idx.normalize()
    out.index.name = "date"
    missing = [c for c in ("open", "high", "low", "close", "volume") if c not in out.columns]
    if missing:
        raise ProviderError(f"{ticker}: missing columns {missing}")
    if "adj_close" not in out.columns:
        # Some sources deliver already-adjusted prices without a separate column.
        log.warning("%s: no adjusted close column; using close as adj_close", ticker)
        out["adj_close"] = out["close"]
    for c in ("dividends", "splits"):
        if c not in out.columns:
            out[c] = 0.0
    out = out[STANDARD_COLUMNS].astype(float)
    return out.sort_index(kind="stable")  # stable: keeps the order of duplicate dates


class DataProvider(abc.ABC):
    """Interface: fetch raw daily OHLCV for one ticker between two dates (inclusive)."""

    name: str = "abstract"

    @abc.abstractmethod
    def fetch(self, ticker: str, start: dt.date, end: dt.date) -> pd.DataFrame: ...

    def version(self) -> str:
        return "n/a"


class YFinanceProvider(DataProvider):
    """Yahoo Finance via ``yfinance``.

    Uses ``Ticker.history(auto_adjust=False, actions=True, repair=False)`` so we receive
    split-adjusted OHLC, a separate split+dividend adjusted close, split-adjusted volume,
    and the dividend/split events. ``repair=False``: we do not let the library silently
    alter prices; our own cleaning logs every change.
    """

    name = "yfinance"

    def fetch(self, ticker: str, start: dt.date, end: dt.date) -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError as e:  # pragma: no cover - yfinance is a core dependency
            raise ProviderError("yfinance is not installed; run `make install`") from e
        end_exclusive = pd.Timestamp(end) + pd.Timedelta(days=1)  # yfinance's end is exclusive
        try:
            df = yf.Ticker(ticker).history(
                start=pd.Timestamp(start).strftime("%Y-%m-%d"),
                end=end_exclusive.strftime("%Y-%m-%d"),
                interval="1d",
                auto_adjust=False,
                actions=True,
                repair=False,
                raise_errors=True,
            )
        except Exception as e:  # network errors, 403 from a proxy, delisted tickers ...
            raise ProviderError(f"{ticker}: yfinance download failed: {type(e).__name__}: {e}") from e
        out = standardise(df, ticker)
        return out.loc[pd.Timestamp(start) : pd.Timestamp(end)]

    def version(self) -> str:
        try:
            import yfinance as yf

            return str(yf.__version__)
        except Exception:  # pragma: no cover
            return "unknown"


class CSVDirectoryProvider(DataProvider):
    """Reads ``<directory>/<TICKER>.csv`` in Yahoo's CSV export format."""

    name = "csv"

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def fetch(self, ticker: str, start: dt.date, end: dt.date) -> pd.DataFrame:
        path = self.directory / f"{ticker}.csv"
        if not path.exists():
            raise ProviderError(f"{ticker}: file not found: {path}")
        df = pd.read_csv(path)
        date_col = next((c for c in df.columns if c.strip().lower() == "date"), None)
        if date_col is None:
            raise ProviderError(f"{ticker}: {path} has no Date column")
        df = df.rename(columns={date_col: "date"})
        out = standardise(df, ticker)
        return out.loc[pd.Timestamp(start) : pd.Timestamp(end)]


class FixtureProvider(DataProvider):
    """Committed synthetic fixtures: long CSV with a ``ticker`` column."""

    name = "fixture"

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._frame: pd.DataFrame | None = None

    def _load(self) -> pd.DataFrame:
        if self._frame is None:
            if not self.path.exists():
                raise ProviderError(f"fixture file not found: {self.path} (run `make fixtures`)")
            self._frame = pd.read_csv(self.path, parse_dates=["date"])
        return self._frame

    def tickers(self) -> list[str]:
        return sorted(self._load()["ticker"].unique())

    def fetch(self, ticker: str, start: dt.date, end: dt.date) -> pd.DataFrame:
        df = self._load()
        sub = df[df["ticker"] == ticker].drop(columns="ticker")
        if sub.empty:
            raise ProviderError(f"{ticker}: not in fixture {self.path}")
        out = standardise(sub, ticker)
        return out.loc[pd.Timestamp(start) : pd.Timestamp(end)]


def make_provider(kind: str, *, fixture_file: str | Path | None = None, csv_dir: str | Path | None = None) -> DataProvider:
    if kind == "yfinance":
        return YFinanceProvider()
    if kind == "csv":
        if csv_dir is None:
            raise ValueError("csv provider needs csv_dir")
        return CSVDirectoryProvider(csv_dir)
    if kind == "fixture":
        if fixture_file is None:
            raise ValueError("fixture provider needs fixture_file")
        return FixtureProvider(fixture_file)
    raise ValueError(f"unknown provider {kind}")
