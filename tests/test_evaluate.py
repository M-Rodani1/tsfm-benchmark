"""Evaluation layer: pooling, contamination test, economics and the end-to-end tables.

The end-to-end test uses a *toy* backend standing in for a TSFM (tests/tsfm_helpers.py) so
that the primary-family and contamination code paths are exercised even though real
weights are unavailable in CI. Nothing produced here is reported anywhere.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tests.tsfm_helpers import ToyBackend
from tsfm_rc.config import load_config
from tsfm_rc.data.panel import load_panel
from tsfm_rc.engine.tsfm_runner import forecast_with_backend
from tsfm_rc.engine.walkforward import build_origins, run_baselines
from tsfm_rc.eval.contamination_test import contamination_delta
from tsfm_rc.eval.economic import backtest
from tsfm_rc.eval.evaluate import evaluate
from tsfm_rc.eval.pooled import paired_pooled, pretest_scales
from tsfm_rc.leakage import perturb_future


def test_pretest_scales_ignore_test_period():
    cfg = load_config("configs/smoke.yaml")
    panel = load_panel(cfg)
    ts = cfg.evaluation.test_start
    a = pretest_scales(panel.daily, ["returns", "rv", "volume"], [1, 20], ts)
    pert = {t: perturb_future(d, pd.Timestamp(ts), seed=1) for t, d in panel.daily.items()}
    b = pretest_scales(pert, ["returns", "rv", "volume"], [1, 20], ts)
    pd.testing.assert_frame_equal(a, b)
    assert (a["scale"] > 0).all()


def test_paired_pooled_hand_example():
    o = pd.to_datetime(["2020-01-01", "2020-01-01", "2020-01-02", "2020-01-02", "2020-01-02"])
    L = pd.DataFrame({
        "ticker": ["A", "B", "A", "B", "A"],
        "origin": o,
        "model": ["m", "m", "m", "m", "r"],
        "loss": [1.0, 3.0, 2.0, 4.0, 1.0],
    })
    L = pd.concat([L, pd.DataFrame({"ticker": ["A", "B"], "origin": o[:2], "model": ["r", "r"], "loss": [0.5, 0.5]})])
    pp = paired_pooled(L, "m", "r", "loss")
    # 2020-01-01: both assets paired -> m mean 2, r mean 0.5; 2020-01-02: only A paired -> 2 vs 1
    assert pp.loc["2020-01-01", "m"] == 2.0 and pp.loc["2020-01-01", "ref"] == 0.5
    assert pp.loc["2020-01-02", "m"] == 2.0 and pp.loc["2020-01-02", "n_assets"] == 1


def test_contamination_delta_identities_and_direction():
    rng = np.random.default_rng(0)
    ref_s, ref_c = rng.gamma(2, 1, 150), rng.gamma(2, 1, 120)
    same = contamination_delta(ref_s, ref_s, ref_c, ref_c, B=200, h_eff=1, rng=rng)
    assert same["delta"] == pytest.approx(0.0) and same["p_one_sided"] == 1.0
    # TSFM 30% better only where it may have seen the data -> Delta > 0, significant
    mem = contamination_delta(0.7 * ref_s, ref_s, ref_c, ref_c, B=500, h_eff=1, rng=rng)
    assert mem["delta"] == pytest.approx(-np.log(0.7))
    assert mem["ci_lo"] > 0 and mem["p_one_sided"] < 0.01
    few = contamination_delta(ref_s[:3], ref_s[:3], ref_c, ref_c, B=50, h_eff=1, rng=rng)
    assert few["flag"] == "insufficient_data"


@pytest.mark.slow
def test_contamination_ci_coverage():
    """Monte Carlo: the 95% CI covers the true Delta about 95% of the time."""
    rng = np.random.default_rng(1)
    true_delta = np.log(1.0) - np.log(0.9)
    cover = 0
    R = 150
    for _ in range(R):
        rs, rc = rng.gamma(2, 1, 200), rng.gamma(2, 1, 200)
        ms, mc = 0.9 * rs * rng.gamma(20, 1 / 20, 200), rc * rng.gamma(20, 1 / 20, 200)
        res = contamination_delta(ms, rs, mc, rc, B=300, h_eff=1, rng=rng)
        cover += res["ci_lo"] <= true_delta <= res["ci_hi"]
    assert 0.88 <= cover / R <= 0.99


def test_backtest_constant_forecast_and_costs():
    idx = pd.bdate_range("2021-01-01", periods=60)
    r = pd.Series(0.5, index=idx)  # +0.5% log return every day
    f = pd.DataFrame({"asset_date": idx[[0, 20, 40]], "y_pred": [1.0, 1.0, 1.0]})
    summ, port = backtest(r, f, target_vol=0.10, max_leverage=2.0, cost_bps=10.0)
    w = 0.10 / (np.sqrt(252 * 1.0) / 100)  # 0.63
    simple = np.exp(0.005) - 1
    assert port.iloc[1] == pytest.approx(w * simple)
    assert port.iloc[0] == pytest.approx(w * simple - 10e-4 * w)  # cost only at the first rebalance
    assert summ["avg_weight"] == pytest.approx(w)
    assert summ["turnover_per_year"] == pytest.approx(w / (len(port) / 252))


@pytest.fixture(scope="module")
def e2e():
    cfg = load_config("configs/smoke.yaml")
    ev = cfg.evaluation.model_copy(update={"stride": 20, "windows": ["expanding"]})
    models = cfg.models.model_copy(update={"lgbm": cfg.models.lgbm.model_copy(update={"n_estimators": 20})})
    stats = cfg.stats.model_copy(update={"n_bootstrap": 100})
    cfg = cfg.model_copy(update={"evaluation": ev, "models": models, "stats": stats})
    panel = load_panel(cfg)
    base = run_baselines(panel.daily, panel.calendar, cfg, n_jobs=1)
    spec = next(s for s in cfg.models.tsfms if s.name == "chronos_bolt_tiny")
    toy = forecast_with_backend(ToyBackend("chronos_bolt_tiny"), spec, panel.daily, build_origins(panel.calendar, cfg), cfg, cache=None)
    status = {"chronos_bolt_tiny": {"status": "AVAILABLE"},
              "timesfm_2p5_200m": {"status": "UNAVAILABLE", "reason": "test"},
              "moirai_1p1_small": {"status": "UNAVAILABLE", "reason": "test"}}
    out = evaluate(pd.concat([base, toy], ignore_index=True), panel.daily, cfg, status)
    return cfg, out


def test_primary_family(e2e):
    cfg, out = e2e
    p = out["dm_primary"]
    assert len(p) == 27
    avail = p[p["status"] == "AVAILABLE"]
    assert set(avail["model"]) == {"chronos_bolt_tiny"} and len(avail) == 9
    assert avail["p_value"].notna().all()
    assert (avail["p_holm"] >= avail["p_value"] - 1e-12).all()
    assert p.loc[p["status"] == "UNAVAILABLE", "p_value"].isna().all()
    assert (avail["start"] >= pd.Timestamp("2024-12-26")).all()  # clean window only


def test_contamination_and_placebo_rows(e2e):
    cfg, out = e2e
    c = out["contamination"]
    tsfm = c[(c["role"] == "tsfm") & (c["status"] == "AVAILABLE")]
    assert len(tsfm) == 9 and tsfm["delta"].notna().all()
    assert (c["role"] == "placebo").sum() == 27  # one placebo per target x horizon x TSFM window set


def test_tables_consistent(e2e):
    cfg, out = e2e
    m = out["metrics"]
    bench = m[(m["model"] == m["r2_benchmark"]) & (m["ticker"] == "POOLED")]
    np.testing.assert_allclose(bench["oos_r2"], 0.0, atol=1e-12)
    mcs = out["mcs"]
    for _, g in mcs.groupby(["period", "target", "horizon", "ticker"]):
        assert g["mcs_pvalue"].max() == 1.0  # the best model always survives
        assert g.loc[g["mean_loss"].idxmin(), "mcs_pvalue"] >= g["mcs_pvalue"].median()
    assert set(out["dm_all"]["period"]) == {"full", "common_clean"}
    assert not out["economic"].empty and "buy_and_hold" in set(out["economic"]["model"])
