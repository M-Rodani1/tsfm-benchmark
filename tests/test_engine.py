"""Walk-forward engine: causality, schedule, windows, targets and determinism."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tsfm_rc.config import load_config
from tsfm_rc.data.panel import load_panel
from tsfm_rc.data.targets import make_target
from tsfm_rc.engine.walkforward import Task, build_origins, qcol, run_baselines, run_task
from tsfm_rc.leakage import perturb_future


@pytest.fixture(scope="module")
def setup():
    cfg = load_config("configs/smoke.yaml")
    ev = cfg.evaluation.model_copy(update={"test_start": pd.Timestamp("2025-06-02").date(), "stride": 10})
    models = cfg.models.model_copy(update={"lgbm": cfg.models.lgbm.model_copy(update={"n_estimators": 20})})
    cfg = cfg.model_copy(update={"evaluation": ev, "models": models})
    panel = load_panel(cfg)
    return cfg, panel, build_origins(panel.calendar, cfg)


def test_engine_is_future_invariant(setup):
    """Scramble all data after a cut date: every forecast made at or before it must be identical."""
    cfg, panel, origins = setup
    d = panel.daily["SYN_GARCH_A"]
    cut = origins[len(origins) // 2].timestamp
    for kind in ("returns", "rv", "volume"):
        task = Task("SYN_GARCH_A", kind, "expanding", tuple(cfg.models.baselines[kind]))
        a = run_task(d, task, origins, cfg)
        b = run_task(perturb_future(d, cut, seed=9), task, origins, cfg)
        keep = a["asset_date"] <= cut
        assert keep.sum() > 0
        cols = ["y_pred"] + [qcol(q) for q in cfg.stats.quantile_levels]
        pd.testing.assert_frame_equal(a.loc[keep, cols].reset_index(drop=True), b.loc[keep, cols].reset_index(drop=True))
        # sanity: the perturbation did change later forecasts, so the test has teeth
        assert not np.allclose(a.loc[~keep, "y_pred"], b.loc[~keep, "y_pred"])


def test_refit_schedule_and_windows(setup):
    cfg, panel, origins = setup
    d = panel.daily["SYN_HAR_A"]
    out = run_task(d, Task("SYN_HAR_A", "rv", "rolling", ("garch", "har")), origins, cfg)
    g = out[(out.model == "garch") & (out.horizon == 1)].reset_index(drop=True)
    k = cfg.models.refit_every["garch"]
    assert g["refit"].tolist() == [i % k == 0 for i in range(len(g))]
    assert out[out.model == "har"]["refit"].all()  # re-fit every origin
    assert (out["n_train"] == cfg.evaluation.rolling_length).all()


def test_y_true_matches_target_and_is_not_used(setup):
    cfg, panel, origins = setup
    d = panel.daily["SYN_GARCH_B"]
    out = run_task(d, Task("SYN_GARCH_B", "volume", "expanding", ("har",)), origins, cfg)
    for h in cfg.targets.horizons:
        sub = out[out.horizon == h]
        tgt = make_target(d, "volume", h).reindex(sub["asset_date"]).to_numpy()
        np.testing.assert_allclose(sub["y_true"].to_numpy(), tgt, equal_nan=True)
    # last origins have no realised 20-day target yet
    assert out[out.horizon == 20]["y_true"].isna().any()


def test_min_train_and_staleness_skip(setup):
    cfg, panel, origins = setup
    d = panel.daily["SYN_GARCH_A"]
    short = d.iloc[: cfg.evaluation.min_train_obs - 1]
    out = run_task(short, Task("X", "returns", "expanding", ("zero",)), origins, cfg)
    assert out.empty or len(out) == 0


def test_run_baselines_deterministic_across_n_jobs(setup):
    cfg, panel, _ = setup
    daily = {t: panel.daily[t] for t in ("SYN_GARCH_A", "SYN_HAR_A")}
    a = run_baselines(daily, panel.calendar, cfg, n_jobs=1)
    b = run_baselines(daily, panel.calendar, cfg, n_jobs=2)
    pd.testing.assert_frame_equal(a, b)
    assert set(a["model"]) == {m for ms in cfg.models.baselines.values() for m in ms}
    h1 = a[(a.horizon == 1) & a.model.isin(["hist_mean", "har", "ar_bic"])]
    assert h1[qcol(0.5)].notna().all()
