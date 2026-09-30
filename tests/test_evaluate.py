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
from tsfm_rc.contamination.windows import windows_for_models
from tsfm_rc.data.panel import load_panel
from tsfm_rc.engine.tsfm_runner import forecast_with_backend
from tsfm_rc.engine.walkforward import (
    build_origins,
    build_primary_origins,
    run_baselines,
    run_primary_baselines,
)
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
    # amendment A4: stride-1 primary pass (reference + placebo baselines, toy TSFM from its clean start)
    base_p = run_primary_baselines(panel.daily, panel.calendar, cfg, n_jobs=4)
    clean_start = windows_for_models(cfg, status)["chronos_bolt_tiny"].clean_start
    toy_p = forecast_with_backend(ToyBackend("chronos_bolt_tiny"), spec, panel.daily,
                                  build_primary_origins(panel.calendar, cfg, start=clean_start), cfg, cache=None)
    fc_primary = pd.concat([base_p, toy_p], ignore_index=True)
    out = evaluate(pd.concat([base, toy], ignore_index=True), panel.daily, cfg, status, fc_primary=fc_primary)
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
    prob = out["probabilistic"]
    assert {"pinball_q10", "pinball_q50", "pinball_q90", "crps_n"} <= set(prob.columns)
    assert (prob["pinball_q50"] > 0).all()


# ------------------------------------------------------------------ amendment A4
def test_primary_family_uses_stride1_clean_window_origins(e2e):
    """dm_primary is built from the stride-1 primary pass only, inside the model's clean window."""
    cfg, out = e2e
    LP = out["losses_primary"]
    p = out["dm_primary"]
    avail = p[p["status"] == "AVAILABLE"]
    assert (avail["stride"] == 1).all() and (avail["method"] == "kv_b1").all()
    assert (avail["h_eff"] == avail["horizon"]).all()  # stride 1: h_eff = h
    cal = pd.DatetimeIndex(sorted(LP["origin"].unique()))
    for r in avail.itertuples(index=False):
        S = LP[(LP["target"] == r.target) & (LP["horizon"] == r.horizon) & (LP["win_chronos_bolt_tiny"] == "clean")]
        pp = paired_pooled(S, r.model, r.reference, f"{r.loss}_n")
        assert r.T == len(pp) and r.T > 100
        assert r.start == pp.index.min() and r.start >= pd.Timestamp("2024-12-26")
        # consecutive trading days: every origin in the window is used, none skipped
        pos = cal.get_indexer(pp.index)
        assert (np.diff(pos) == 1).all()
        # far more origins than the stride-20 main pass has in the same window
        main_clean = out["losses"][(out["losses"]["target"] == r.target) & (out["losses"]["horizon"] == r.horizon)
                                   & (out["losses"]["model"] == r.model) & (out["losses"]["win_chronos_bolt_tiny"] == "clean")]
        assert r.T > 5 * main_clean["origin"].nunique()


def test_contamination_clean_side_from_primary_pass(e2e):
    cfg, out = e2e
    c = out["contamination"]
    L, LP = out["losses"], out["losses_primary"]
    for r in c[(c["status"] == "AVAILABLE")].itertuples(index=False):
        S = LP[(LP["target"] == r.target) & (LP["horizon"] == r.horizon) & (LP[f"win_{r.windows_of}"] == "clean")]
        Sm = L[(L["target"] == r.target) & (L["horizon"] == r.horizon) & (L["window"] == "expanding")
               & (L[f"win_{r.windows_of}"] == "seen")]
        loss = {"returns": "mse_n", "rv": "qlike_n", "volume": "mse_n"}[r.target]
        assert r.T_clean == len(paired_pooled(S, r.model, r.reference, loss))
        assert r.T_seen == len(paired_pooled(Sm, r.model, r.reference, loss))


def test_primary_rows_without_primary_pass_are_flagged():
    from tsfm_rc.eval.evaluate import dm_primary

    cfg = load_config("configs/smoke.yaml")
    status = {s.name: {"status": "AVAILABLE"} for s in cfg.models.tsfms}
    p = dm_primary(None, cfg, status)
    assert (p["flag"] == "no_primary_pass_forecasts").all() and p["p_value"].isna().all()


# ------------------------------------------------------------------ Audit-01 fix 3: oracle-ratio CIs
def _synthetic_forecasts(scale_b: float, n_series: int = 3, n_origins: int = 300, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    origins = pd.bdate_range("2020-01-01", periods=n_origins)
    for s in range(n_series):
        truth = rng.gamma(4, 0.25, n_origins)
        y = truth * rng.gamma(4, 0.25, n_origins)
        for model, pred in [("oracle", truth), ("good", truth * rng.gamma(400, 1 / 400, n_origins)), ("biased", truth * scale_b)]:
            for o, yt, p, lat in zip(origins, y, pred, truth, strict=True):
                rows.append({"ticker": f"S{s}", "target": "rv", "horizon": 1, "model": model, "origin": o,
                             "y_true": yt, "y_pred": p, "y_latent": lat})
    return pd.DataFrame(rows)


def test_synthetic_oracle_ratio_has_bootstrap_ci_and_honest_wording():
    from tsfm_rc.eval.evaluate import synthetic_table
    from tsfm_rc.reports.results_md import _oracle_ratio_text

    cfg = load_config("configs/smoke.yaml")
    S = synthetic_table(_synthetic_forecasts(0.7), cfg, kappa=1.0).set_index("model")
    good, biased = S.loc["good"], S.loc["biased"]
    assert good["ratio_to_oracle_lo"] < good["ratio_to_oracle"] < good["ratio_to_oracle_hi"]
    assert good["ratio_ci_covers_1"]  # a near-oracle model is indistinguishable from it
    assert biased["ratio_to_oracle_lo"] > 1 and not biased["ratio_ci_covers_1"]  # a 30% bias is detected
    assert np.isnan(S.loc["oracle", "ratio_to_oracle_lo"])
    below = pd.Series({"ratio_to_oracle": 0.996, "ratio_to_oracle_lo": 0.98, "ratio_to_oracle_hi": 1.01})
    assert _oracle_ratio_text(below) == "0.996× oracle loss, 95% CI [0.980, 1.010]: below 1 only by sampling noise"
    above = pd.Series({"ratio_to_oracle": 1.2, "ratio_to_oracle_lo": 1.1, "ratio_to_oracle_hi": 1.3})
    assert _oracle_ratio_text(above) == "1.200× oracle loss, 95% CI [1.100, 1.300]"
