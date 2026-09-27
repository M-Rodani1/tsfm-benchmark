"""Clean / possibly-seen window logic and the synthetic-control experiment."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tsfm_rc.config import load_config
from tsfm_rc.contamination.synthetic_control import calibrate, run_synthetic_control
from tsfm_rc.contamination.windows import common_clean_start, windows_for_models
from tsfm_rc.data.panel import load_panel


@pytest.fixture(scope="module")
def cfg():
    return load_config("configs/default.yaml")


def test_windows_use_release_date_and_buffer(cfg):
    w = windows_for_models(cfg)
    cb = w["chronos_bolt_tiny"]
    assert cb.effective_release == pd.Timestamp("2024-11-26")
    assert cb.clean_start == pd.Timestamp("2024-12-26")
    origins = pd.Series(pd.to_datetime(["2014-06-02", "2016-01-04", "2024-11-01", "2024-11-20", "2024-12-10", "2025-01-06"]))
    ends = pd.Series(pd.to_datetime(["2014-06-30", "2016-02-01", "2024-11-25", "2024-12-18", "2025-01-08", "2025-02-03"]))
    lab = cb.label(origins, ends).tolist()
    assert lab == ["pre_test", "seen", "seen", "gap", "gap", "clean"]


def test_label_straddling_release_is_excluded(cfg):
    cb = windows_for_models(cfg)["chronos_bolt_tiny"]
    # 20-day target starting before release but ending after it: neither seen nor clean
    lab = cb.label(pd.Series([pd.Timestamp("2024-11-15")]), pd.Series([pd.Timestamp("2024-12-13")]))
    assert lab.iloc[0] == "gap"


def test_weights_date_after_release_moves_windows(cfg):
    st = {"chronos_bolt_tiny": {"weights_commit_date": "2025-03-01"}}
    cb = windows_for_models(cfg, st)["chronos_bolt_tiny"]
    assert cb.effective_release == pd.Timestamp("2025-03-01")
    assert cb.clean_start == pd.Timestamp("2025-03-31")
    # an older weights date never moves the window earlier
    st = {"chronos_bolt_tiny": {"weights_commit_date": "2024-01-01"}}
    assert windows_for_models(cfg, st)["chronos_bolt_tiny"].effective_release == pd.Timestamp("2024-11-26")


def test_common_clean_start(cfg):
    w = windows_for_models(cfg)
    assert common_clean_start(w) == pd.Timestamp("2025-10-15")  # TimesFM 2.5 released 2025-09-15
    assert common_clean_start(w, ["chronos_bolt_tiny", "moirai_1p1_small"]) == pd.Timestamp("2024-12-26")
    assert common_clean_start(w, []) == pd.Timestamp("2025-10-15")  # none available -> configured


@pytest.fixture(scope="module")
def synth():
    cfg = load_config("configs/smoke.yaml")
    sc = cfg.synthetic.model_copy(update={"n_series": 2, "n_days": 1400, "test_days": 200, "intraday_steps": 60})
    ev = cfg.evaluation.model_copy(update={"stride": 5})
    models = cfg.models.model_copy(update={"lgbm": cfg.models.lgbm.model_copy(update={"n_estimators": 20})})
    cfg = cfg.model_copy(update={"synthetic": sc, "evaluation": ev, "models": models})
    panel = load_panel(cfg)
    fc, meta = run_synthetic_control(cfg, panel.daily["SYN_GARCH_A"])
    return cfg, fc, meta


def test_calibration_is_stationary():
    cfg = load_config("configs/smoke.yaml")
    g, h, v = calibrate(load_panel(cfg).daily["SYN_HAR_A"])
    assert 0 < g.alpha + g.beta < 1 and g.omega > 0
    assert 0 < h.persistence <= 0.95 + 1e-12 and h.c > 0 and min(h.b_d, h.b_w, h.b_m) >= 0


def test_synthetic_control_outputs(synth):
    cfg, fc, meta = synth
    assert "oracle" in set(fc["model"])
    assert set(fc["ticker"]) == {"SIM_GARCH_00", "SIM_HAR_01"}
    rv = fc[fc["target"] == "rv"]
    assert rv["y_latent"].notna().sum() > 0
    assert fc[fc["target"] != "rv"]["y_latent"].isna().all()
    ret = fc[(fc.model == "oracle") & (fc.target == "returns")]
    g = meta["garch_spec"]
    np.testing.assert_allclose(ret["y_pred"] / ret["horizon"], g["mu"], rtol=0, atol=0.5)


def test_oracle_beats_baselines_on_latent_variance(synth):
    """Against the TRUE variance, the oracle must have the lowest QLIKE (sanity check)."""
    cfg, fc, _ = synth
    rv = fc[(fc.target == "rv") & (fc.horizon == 5) & fc.y_latent.notna()]
    oracle_pred = rv[rv.model == "oracle"].set_index(["ticker", "origin"])["y_pred"]
    # the oracle targets E[GK] = kappa * sigma2; compare against kappa * latent
    kappa = synth[2]["kappa"]

    def ql(df):
        y = kappa * df["y_latent"]
        f = df["y_pred"]
        return float(np.mean(y / f - np.log(y / f) - 1))

    scores = {m: ql(g) for m, g in rv.groupby("model")}
    assert min(scores, key=scores.get) == "oracle", scores
    assert len(oracle_pred) > 0
