"""Synthetic generators, oracle forecasts and committed fixtures."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from tsfm_rc.config import load_config
from tsfm_rc.data.panel import load_panel
from tsfm_rc.data.synthetic import (
    FIXTURE_SPECS,
    GarchSpec,
    HarSpec,
    VolumeSpec,
    ex_dividend_dates,
    garch_expected_variance,
    har_expected_variance,
    make_fixture_panel,
    simulate_asset,
    simulate_garch,
    simulate_har,
    trading_calendar,
    volume_expected_logvol,
)
from tsfm_rc.data.targets import log_returns_pct
from tsfm_rc.hashing import sha256_file
from tsfm_rc.paths import FIXTURE_DIR


def test_committed_fixture_matches_manifest_and_generator():
    man = json.loads((FIXTURE_DIR / "MANIFEST.json").read_text())
    for f, digest in man["files"].items():
        assert sha256_file(FIXTURE_DIR / f) == digest
    ohlcv, latent = make_fixture_panel(man["seed"])
    committed = pd.read_csv(FIXTURE_DIR / "synthetic_ohlcv.csv", parse_dates=["date"])
    assert list(committed.columns) == list(ohlcv.columns)
    assert (committed["ticker"] == ohlcv["ticker"]).all()
    num = ["open", "high", "low", "close", "adj_close", "volume"]
    np.testing.assert_allclose(committed[num].to_numpy(), ohlcv[num].to_numpy(), rtol=0, atol=1e-5)
    lat = pd.read_csv(FIXTURE_DIR / "synthetic_latent.csv", parse_dates=["date"])
    np.testing.assert_allclose(lat["sigma2"].to_numpy(), latent["sigma2"].to_numpy(), atol=1e-7)


def test_garch_simulation_recursion_and_oracle():
    spec = GarchSpec(0.05, 0.1, 0.85, mu=0.02)
    sim = simulate_garch(spec, 400, np.random.default_rng(0), steps=50)
    eps = sim["r_true"] - spec.mu
    s2 = sim["sigma2"].to_numpy()
    # recursion: sigma2_{t+1} = omega + alpha eps_t^2 + beta sigma2_t
    np.testing.assert_allclose(sim["sigma2_next"].to_numpy()[:-1], s2[1:])
    np.testing.assert_allclose(s2[1:], spec.omega + spec.alpha * eps.to_numpy()[:-1] ** 2 + spec.beta * s2[:-1], rtol=1e-10)
    # oracle: iterate E[sigma2_{t+i+1}] = omega + (alpha+beta) E[sigma2_{t+i}]
    path = garch_expected_variance(spec, np.array(3.0), 5)
    ref = [3.0]
    for _ in range(4):
        ref.append(spec.omega + spec.persistence * ref[-1])
    np.testing.assert_allclose(path, ref)


def test_garch_oracle_by_monte_carlo():
    spec = GarchSpec(0.05, 0.1, 0.85, mu=0.0)
    rng = np.random.default_rng(5)
    n_paths, h = 200_000, 4
    s2 = np.full(n_paths, 2.5)  # sigma2_{t+1} known
    out = []
    for _ in range(h):
        out.append(s2.mean())
        z = rng.standard_normal(n_paths)
        s2 = spec.omega + spec.alpha * s2 * z**2 + spec.beta * s2
    np.testing.assert_allclose(out, garch_expected_variance(spec, np.array(2.5), h), rtol=0.01)


def test_har_simulation_and_oracle():
    spec = HarSpec(0.1, 0.35, 0.35, 0.2, shock_sd=0.5)
    sim = simulate_har(spec, 3000, np.random.default_rng(1), steps=30)
    assert sim["sigma2"].mean() == pytest.approx(spec.uncond_var, rel=0.1)
    past = sim["sigma2"].to_numpy()[:100]
    path = har_expected_variance(spec, past, 3)
    step1 = spec.c + spec.b_d * past[-1] + spec.b_w * past[-5:].mean() + spec.b_m * past[-22:].mean()
    assert path[0] == pytest.approx(step1)
    assert sim["sigma2_next"].iloc[99] == pytest.approx(step1)
    ext = np.append(past, step1)
    assert path[1] == pytest.approx(spec.c + spec.b_d * ext[-1] + spec.b_w * ext[-5:].mean() + spec.b_m * ext[-22:].mean())


def test_volume_oracle():
    spec = VolumeSpec()
    dates = trading_calendar("2024-01-01", "2024-01-31")
    exp = volume_expected_logvol(spec, 0.3, -0.1, dates[:3])
    manual = [spec.level + spec.dow[d.dayofweek] + spec.phi_fast ** i * 0.3 + spec.phi_slow ** i * -0.1 for i, d in enumerate(dates[:3], 1)]
    np.testing.assert_allclose(exp, manual)


def test_simulated_ohlc_is_valid():
    dates = trading_calendar("2020-01-01", "2021-12-31")
    ohlcv, latent = simulate_asset(FIXTURE_SPECS["SYN_GARCH_A"][0], VolumeSpec(), dates, np.random.default_rng(2), steps=60)
    assert (ohlcv["high"] >= ohlcv[["open", "close"]].max(axis=1)).all()
    assert (ohlcv["low"] <= ohlcv[["open", "close"]].min(axis=1)).all()
    assert (ohlcv["open"].iloc[1:].to_numpy() == ohlcv["close"].iloc[:-1].to_numpy()).all()  # no overnight gap
    assert len(latent) == len(dates)


def test_fixture_dividends_do_not_affect_adjusted_returns():
    ohlcv, _ = make_fixture_panel()
    q = ohlcv[ohlcv["ticker"] == "SYN_QUIRKS"].set_index("date")
    q = q[~q.index.duplicated(keep="last")]
    q = q[q.index.dayofweek < 5]
    ex = ex_dividend_dates(q.index)
    r_adj = log_returns_pct(q["adj_close"])
    r_raw = log_returns_pct(q["close"])
    d = ex[10]
    assert r_raw.loc[d] - r_adj.loc[d] == pytest.approx(100 * np.log(1 - 0.005), abs=1e-3)
    assert (q["dividends"] > 0).sum() >= 60


def test_smoke_panel_loads_with_cleaning_report():
    cfg = load_config("configs/smoke.yaml")
    p = load_panel(cfg)
    assert set(p.tickers) == set(cfg.data.tickers)
    issues = set(p.cleaning.to_frame()["issue"])
    assert {"weekend_row", "duplicate_date", "stale_row", "ohlc_violation", "zero_volume", "suspect_split", "missing_day"} <= issues
    p2 = load_panel(cfg)
    assert p.panel_hash == p2.panel_hash and p.raw_hash == p2.raw_hash
    assert p.source == "fixture" and not p.unavailable


def test_panel_marks_uncached_real_data_unavailable(tmp_path):
    cfg = load_config("configs/default.yaml", output_dir=str(tmp_path))
    cfg = cfg.model_copy(update={"data": cfg.data.model_copy(update={"raw_dir": tmp_path, "tickers": ["SPY", "QQQ"]})})
    p = load_panel(cfg, allow_fetch=False)
    assert p.tickers == [] and set(p.unavailable) == {"SPY", "QQQ"}
    assert "make fetch-data" in p.unavailable["SPY"]
