"""Cleaning rules: every rule fires on a crafted example and is logged."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsfm_rc.data.cleaning import clean_ohlcv, flag_missing_days


def _frame(n=10):
    idx = pd.bdate_range("2021-03-01", periods=n)
    c = np.linspace(100, 110, n)
    return pd.DataFrame(
        {"open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "adj_close": c, "volume": 1e6,
         "dividends": 0.0, "splits": 0.0},
        index=idx,
    )


def test_clean_data_unchanged_and_empty_report():
    df = _frame()
    out, rep = clean_ohlcv(df, "X")
    pd.testing.assert_frame_equal(out, df.rename_axis("date"))
    assert rep.to_frame().empty


def test_each_rule_fires():
    df = _frame(12)
    idx = df.index
    df.loc[idx[1], "close"] = -1.0                                       # nonpositive
    df.loc[idx[2], ["open", "high", "low", "close"]] = 100.0
    df.loc[idx[2], "volume"] = 0.0                                        # stale
    df.loc[idx[3], "high"] = df.loc[idx[3], "close"] * 0.9                # ohlc violation
    df.loc[idx[4], "volume"] = 0.0                                        # zero volume
    df.loc[idx[8]:, ["open", "high", "low", "close", "adj_close"]] *= 0.5  # suspect split
    split_price = df.loc[idx[8], "adj_close"]
    wk = df.iloc[[5]].copy()
    wk.index = pd.DatetimeIndex([pd.Timestamp("2021-03-06")])           # Saturday
    dup = df.iloc[[6]].copy()
    dup["close"] = 999.0
    df = pd.concat([df.iloc[:6], dup, df.iloc[6:], wk]).sort_index(kind="stable")

    out, rep = clean_ohlcv(df, "X")
    issues = rep.to_frame().set_index("issue")
    for issue in ("nonpositive_price", "stale_row", "ohlc_violation", "zero_volume", "suspect_split", "weekend_row", "duplicate_date"):
        assert issue in issues.index, issue
    assert idx[1] not in out.index and idx[2] not in out.index
    assert out.loc[idx[3], "high"] >= out.loc[idx[3], ["open", "close"]].max()
    assert np.isnan(out.loc[idx[4], "volume"])
    assert out.loc[idx[6], "close"] != 999.0          # the later copy was kept
    assert out.index.is_unique and (out.index.dayofweek < 5).all()
    # split flagged but NOT altered
    assert out.loc[idx[8], "adj_close"] == split_price
    assert "flagged_only" in issues.loc["suspect_split", "action"]


def test_flag_missing_days_uses_union_calendar():
    a = _frame(10)
    b = a.drop(a.index[4])
    cal, rep = flag_missing_days({"A": a, "B": b})
    assert len(cal) == 10
    f = rep.to_frame()
    assert list(f["ticker"]) == ["B"] and f["date"].iloc[0] == a.index[4]
    # days outside an asset's life are not "missing"
    c = a.iloc[5:]
    _, rep2 = flag_missing_days({"A": a, "C": c})
    assert rep2.to_frame().empty


def test_report_summary_counts():
    df = _frame()
    df.loc[df.index[:3], "volume"] = 0.0
    _, rep = clean_ohlcv(df, "Z")
    s = rep.summary()
    assert int(s.loc[s["issue"] == "zero_volume", "count"].iloc[0]) == 3
