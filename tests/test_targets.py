"""Target construction: returns, Garman-Klass variance, log volume, h-step aggregation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tsfm_rc.data.synthetic import gk_discretisation_factor
from tsfm_rc.data.targets import (
    GK_CONST,
    aggregate_path,
    daily_series,
    garman_klass_variance,
    horizon_target,
    log_returns_pct,
    make_target,
    parkinson_variance,
)
from tsfm_rc.leakage import assert_future_invariant
from tsfm_rc.origin import ForecastOrigin


def S(*v):
    return pd.Series(v, dtype=float)


def test_gk_constant():
    assert GK_CONST == pytest.approx(0.3862943611198906)


def test_gk_known_value_by_hand():
    # O=100, H=102, L=99, C=101
    hl, co = np.log(102 / 99), np.log(101 / 100)
    expected = 1e4 * (0.5 * hl**2 - (2 * np.log(2) - 1) * co**2)
    got = garman_klass_variance(S(100), S(102), S(99), S(101)).iloc[0]
    assert got == pytest.approx(expected, rel=1e-12)
    assert got == pytest.approx(4.0735, abs=1e-3)  # by hand: 1e4*(0.5*0.029853^2 - 0.386294*0.0099503^2) = 4.4561 - 0.3825


def test_parkinson_known_value():
    got = parkinson_variance(S(102), S(99)).iloc[0]
    assert got == pytest.approx(1e4 * np.log(102 / 99) ** 2 / (4 * np.log(2)), rel=1e-12)


def test_gk_nonnegative_for_valid_ohlc_and_nan_for_zero_range():
    rng = np.random.default_rng(0)
    n = 5000
    lo = 100 * np.exp(rng.uniform(-0.05, 0, n))
    hi = lo * np.exp(rng.uniform(0, 0.1, n))
    o = lo + (hi - lo) * rng.uniform(size=n)
    c = lo + (hi - lo) * rng.uniform(size=n)
    gk = garman_klass_variance(pd.Series(o), pd.Series(hi), pd.Series(lo), pd.Series(c))
    assert (gk >= 0).all()
    # worst case |ln C/O| = ln H/L gives the lower bound (0.5 - GK_CONST) ln(H/L)^2
    assert (gk >= 1e4 * (0.5 - GK_CONST) * np.log(hi / lo) ** 2 - 1e-9).all()
    assert np.isnan(garman_klass_variance(S(100), S(100), S(100), S(100)).iloc[0])


def test_gk_unbiased_and_more_efficient_than_parkinson_under_brownian_motion():
    """Garman & Klass (1980): under driftless BM, GK is unbiased and has lower variance.

    With discrete monitoring (steps points) both are biased low by the same range
    effect; we compare against the Monte-Carlo discretisation factor.
    """
    rng = np.random.default_rng(1)
    n, steps, sigma = 20000, 390, 1.0  # sigma in % per day
    Z = rng.standard_normal((n, steps)) * sigma / np.sqrt(steps)
    path = np.cumsum(Z, axis=1)
    p0 = 100 * np.log(50.0)
    o = np.exp(np.full(n, p0) / 100)
    c = np.exp((p0 + path[:, -1]) / 100)
    h = np.exp((p0 + np.maximum(path.max(axis=1), 0)) / 100)
    lo = np.exp((p0 + np.minimum(path.min(axis=1), 0)) / 100)
    gk = garman_klass_variance(pd.Series(o), pd.Series(h), pd.Series(lo), pd.Series(c))
    pk = parkinson_variance(pd.Series(h), pd.Series(lo))
    cc = (100 * np.log(c / o)) ** 2
    kappa = gk_discretisation_factor(steps)
    assert 0.88 < kappa < 0.94
    assert gk.mean() == pytest.approx(kappa * sigma**2, rel=0.02)
    assert cc.mean() == pytest.approx(sigma**2, rel=0.03)
    # efficiency ordering (theory: var ratio ~ 1/7.4 vs ~ 1/5.2 of close-to-close)
    assert gk.var() < pk.var() < cc.var()


def test_log_returns_pct():
    p = S(100, 110, 99)
    r = log_returns_pct(p)
    assert np.isnan(r.iloc[0])
    assert r.iloc[1] == pytest.approx(100 * np.log(1.1))
    assert r.iloc[2] == pytest.approx(100 * np.log(99 / 110))


def test_horizon_target_uses_rows_after_origin():
    x = pd.Series(np.arange(1.0, 11.0))  # 1..10
    y = horizon_target(x, 3, "sum")
    # row 0 -> rows 1,2,3 -> 2+3+4
    assert y.iloc[0] == 9.0
    assert y.iloc[6] == 8 + 9 + 10
    assert y.iloc[7:].isna().all()  # window runs past data
    m = horizon_target(x, 2, "mean")
    assert m.iloc[0] == 2.5


def test_horizon_target_nan_propagates():
    x = pd.Series([1.0, 2.0, np.nan, 4.0, 5.0, 6.0])
    y = horizon_target(x, 2, "mean")
    assert np.isnan(y.iloc[0]) and np.isnan(y.iloc[1])  # windows containing row 2
    assert y.iloc[2] == 4.5


@pytest.mark.parametrize("h", [1, 5, 20])
def test_make_target_matches_explicit_loop(h):
    rng = np.random.default_rng(h)
    idx = pd.bdate_range("2020-01-01", periods=80)
    daily = pd.DataFrame({"r": rng.normal(size=80), "gk": rng.gamma(2, 1, 80), "logvol": rng.normal(15, 1, 80)}, index=idx)
    for kind, col, agg in [("returns", "r", np.sum), ("rv", "gk", np.mean), ("volume", "logvol", np.mean)]:
        y = make_target(daily, kind, h)
        for i in (0, 10, 80 - h - 1):
            assert y.iloc[i] == pytest.approx(agg(daily[col].iloc[i + 1 : i + 1 + h]))
        assert y.iloc[80 - h :].isna().all()


def test_aggregate_path():
    p = np.array([[1.0, 2.0, 3.0, 4.0]])
    assert aggregate_path(p, "returns", 3)[0] == 6.0
    assert aggregate_path(p, "rv", 2)[0] == 1.5
    with pytest.raises(ValueError):
        aggregate_path(p, "volume", 5)


def _ohlcv(n=300, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2019-01-01", periods=n)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = c * np.exp(rng.normal(0, 0.003, n))
    h = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.005, n)))
    lo = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.005, n)))
    v = np.exp(rng.normal(15, 0.3, n))
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c, "adj_close": c, "volume": v}, index=idx)


@pytest.mark.filterwarnings("ignore:invalid value encountered in log")  # scrambled future OHLC
def test_daily_series_is_causal():
    df = _ohlcv()
    origin = ForecastOrigin(df.index[200])

    def fn(data, o):
        return o.history(daily_series(data))[["r", "gk", "logvol", "log_gk_in", "logvol_in"]]

    assert_future_invariant(fn, df, origin)


def test_daily_series_ffill_inputs_only():
    df = _ohlcv(50)
    df.iloc[10, df.columns.get_loc("high")] = df.iloc[10]["low"] = df.iloc[10]["open"] = df.iloc[10]["close"]
    df.iloc[20, df.columns.get_loc("volume")] = np.nan
    d = daily_series(df)
    assert np.isnan(d["gk"].iloc[10]) and d["log_gk_in"].iloc[10] == d["log_gk_in"].iloc[9]
    assert np.isnan(d["logvol"].iloc[20]) and d["logvol_in"].iloc[20] == d["logvol_in"].iloc[19]
