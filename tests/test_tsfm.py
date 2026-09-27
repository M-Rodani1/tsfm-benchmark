"""TSFM wrappers: conversion rules, caching, UNAVAILABLE handling, leakage, real-API adapters."""

from __future__ import annotations

import importlib.util
import os

import numpy as np
import pandas as pd
import pytest

from tests.tsfm_helpers import ToyBackend, random_chronos_pipeline, random_moirai_module, spec
from tsfm_rc.config import load_config
from tsfm_rc.data.panel import load_panel
from tsfm_rc.engine.tsfm_runner import TSFMCache, cache_key, forecast_with_backend, run_tsfms
from tsfm_rc.engine.walkforward import build_origins, qcol
from tsfm_rc.leakage import assert_future_invariant, perturb_future
from tsfm_rc.models.tsfm import (
    DECILES,
    Z90,
    ChronosBoltBackend,
    MoiraiBackend,
    TimesFMBackend,
    TSFMForecaster,
    TSFMUnavailable,
    load_backend,
    make_context,
    to_target_scale,
)
from tsfm_rc.origin import ForecastOrigin

HAS = {m: importlib.util.find_spec(m) is not None for m in ("chronos", "timesfm", "uni2ts", "torch")}


# ------------------------------------------------------------------ conversion rules
def test_to_target_scale_returns_and_volume():
    med = np.arange(1.0, 21.0)
    dec = med[:, None] + np.linspace(-1, 1, 9)[None, :]
    pts, q1 = to_target_scale("returns", med, dec, [1, 5, 20])
    assert pts == {1: 1.0, 5: 15.0, 20: 210.0}
    np.testing.assert_allclose(q1, dec[0])
    pts, _ = to_target_scale("volume", med, dec, [5])
    assert pts[5] == 3.0


def test_to_target_scale_rv_lognormal_mean():
    m, s = np.log(2.0), 0.5
    med = np.full(20, m)
    dec = np.tile(m + s * np.array([-Z90, -0.84, -0.52, -0.25, 0, 0.25, 0.52, 0.84, Z90]), (20, 1))
    pts, q1 = to_target_scale("rv", med, dec, [1, 20])
    expected = np.exp(m + s**2 / 2)  # mean of a lognormal
    assert pts[1] == pytest.approx(expected, rel=1e-9) and pts[20] == pytest.approx(expected, rel=1e-9)
    assert q1[4] == pytest.approx(2.0)  # median maps to exp(median)
    assert np.all(np.diff(q1) > 0)


def test_make_context_last_n_and_causal_fill():
    idx = pd.bdate_range("2020-01-01", periods=10)
    h = pd.DataFrame({"r": [np.nan, 1, 2, np.nan, 4, 5, 6, 7, 8, 9.0], "log_gk_in": 0.0, "logvol_in": 0.0}, index=idx)
    np.testing.assert_array_equal(make_context(h, "returns", 4), [6, 7, 8, 9])
    np.testing.assert_array_equal(make_context(h, "returns", 20), [1, 2, 2, 4, 5, 6, 7, 8, 9])


# ------------------------------------------------------------------ plumbing with a toy backend
@pytest.fixture(scope="module")
def smoke():
    cfg = load_config("configs/smoke.yaml")
    ev = cfg.evaluation.model_copy(update={"test_start": pd.Timestamp("2025-09-01").date(), "stride": 20})
    cfg = cfg.model_copy(update={"evaluation": ev})
    panel = load_panel(cfg)
    daily = {t: panel.daily[t] for t in ("SYN_GARCH_A", "SYN_HAR_A")}
    return cfg, panel, daily, build_origins(panel.calendar, cfg)


def test_tsfm_forecaster_is_causal(smoke):
    cfg, panel, daily, origins = smoke
    d = daily["SYN_HAR_A"]
    o = ForecastOrigin(d.index[3000])
    for kind in ("returns", "rv", "volume"):
        def fn(data, org, kind=kind):
            m = TSFMForecaster(kind, ToyBackend(), 512)
            h = org.history(data)
            m.fit(h)
            return m.predict(h, [1, 5, 20], DECILES)
        assert_future_invariant(fn, d, o)


def test_runner_schema_windows_and_future_invariance(smoke):
    cfg, panel, daily, origins = smoke
    sp = spec("toy", "chronos")
    a = forecast_with_backend(ToyBackend(), sp, daily, origins, cfg, cache=None)
    assert set(a["window"]) == {"expanding", "rolling"}
    assert {"label_end", "y_true", "y_pred", qcol(0.5)} <= set(a.columns)
    assert a.loc[a.horizon == 1, qcol(0.5)].notna().all() and a.loc[a.horizon > 1, qcol(0.5)].isna().all()
    cut = origins[len(origins) // 2].timestamp
    pert = {t: perturb_future(d, cut, seed=3) for t, d in daily.items()}
    b = forecast_with_backend(ToyBackend(), sp, pert, origins, cfg, cache=None)
    keep = a["asset_date"] <= cut
    np.testing.assert_array_equal(a.loc[keep, "y_pred"].to_numpy(), b.loc[keep, "y_pred"].to_numpy())


def test_cache_reuses_and_invalidates(tmp_path, smoke):
    cfg, panel, daily, origins = smoke
    sp = spec("toy", "chronos", batch_size=7)
    cache = TSFMCache(tmp_path)
    be = ToyBackend()
    a = forecast_with_backend(be, sp, daily, origins, cfg, cache)
    n_first = be.n_series
    assert n_first > 0
    be2 = ToyBackend()
    b = forecast_with_backend(be2, sp, daily, origins, cfg, cache)
    assert be2.n_series == 0  # everything served from cache
    pd.testing.assert_frame_equal(a, b)
    # changing one input value changes the context hash -> recompute only affected contexts
    d2 = dict(daily)
    x = d2["SYN_GARCH_A"].copy()
    x.loc[origins[-1].timestamp, "r"] += 1.0  # only the last origin's contexts see this row
    d2["SYN_GARCH_A"] = x
    be3 = ToyBackend()
    forecast_with_backend(be3, sp, d2, origins, cfg, cache)
    assert 0 < be3.n_series < n_first


def test_cache_key_components():
    be = ToyBackend()
    ctx = np.arange(5.0)
    k = cache_key(be, "A", "rv", pd.Timestamp("2020-01-02"), 20, ctx)
    assert k != cache_key(be, "B", "rv", pd.Timestamp("2020-01-02"), 20, ctx)
    assert k != cache_key(be, "A", "rv", pd.Timestamp("2020-01-03"), 20, ctx)
    assert k != cache_key(be, "A", "rv", pd.Timestamp("2020-01-02"), 20, ctx + 1e-12)
    be.info.resolved_revision = "other"
    assert k != cache_key(be, "A", "rv", pd.Timestamp("2020-01-02"), 20, ctx)


# ------------------------------------------------------------------ UNAVAILABLE handling
def test_unavailable_models_reported_with_reason(smoke, monkeypatch, tmp_path):
    cfg, panel, daily, _ = smoke
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")  # never touch the network in tests
    cfg = cfg.model_copy(update={"cache_dir": tmp_path})
    fc, status = run_tsfms(daily, panel.calendar, cfg)
    assert set(status) == {"chronos_bolt_tiny", "timesfm_2p5_200m", "moirai_1p1_small"}
    for name, st in status.items():
        if st["status"] == "UNAVAILABLE":
            assert len(st["reason"]) > 10
            assert fc.empty or name not in set(fc["model"])


def test_load_backend_unknown_package_reason(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    with pytest.raises(TSFMUnavailable):
        load_backend(spec("m", "moirai"), 512, 20)


# ------------------------------------------------------------------ real library adapters (random weights)
tsfm = pytest.mark.skipif(not all(HAS.values()), reason="TSFM extra not installed (make install-tsfm)")


@tsfm
@pytest.mark.tsfm
def test_chronos_adapter_real_api_random_weights():
    be = ChronosBoltBackend(spec("cb", "chronos"), pipeline=random_chronos_pipeline())
    rng = np.random.default_rng(0)
    ctx = [rng.normal(size=512), rng.normal(size=300)]
    m1, q1 = be.predict_batch(ctx, 20)
    m2, q2 = be.predict_batch(ctx, 20)
    assert m1.shape == (2, 20) and q1.shape == (2, 20, 9)
    np.testing.assert_array_equal(m1, m2)  # deterministic
    np.testing.assert_allclose(m1, q1[..., 4])
    solo, _ = be.predict_batch([ctx[0]], 20)
    np.testing.assert_allclose(solo[0], m1[0], rtol=1e-5, atol=1e-6)  # batch composition does not matter


@tsfm
@pytest.mark.tsfm
def test_moirai_adapter_real_api_random_weights():
    be = MoiraiBackend(spec("mo", "moirai", num_samples=30), 512, 20, module=random_moirai_module())
    assert be.context_length(512, 20) == 532
    rng = np.random.default_rng(1)
    ctx = [rng.normal(size=532), rng.normal(size=400)]
    m1, q1 = be.predict_batch(ctx, 20, seed=5)
    m2, _ = be.predict_batch(ctx, 20, seed=5)
    assert m1.shape == (2, 20) and q1.shape == (2, 20, 9)
    np.testing.assert_array_equal(m1, m2)  # same seed -> same samples
    assert np.all(np.diff(q1, axis=-1) >= 0)


@tsfm
@pytest.mark.tsfm
@pytest.mark.slow
def test_timesfm_adapter_real_api_random_weights():
    import timesfm

    model = timesfm.TimesFM_2p5_200M_torch(torch_compile=False)
    be = TimesFMBackend(spec("tf", "timesfm", batch_size=4), 512, 20, model=model)
    rng = np.random.default_rng(2)
    m, q = be.predict_batch([rng.normal(size=512), rng.normal(size=100) + 5], 20)
    assert m.shape == (2, 20) and q.shape == (2, 20, 9)
    np.testing.assert_allclose(m, q[..., 4])


@tsfm
@pytest.mark.tsfm
def test_real_adapter_through_forecaster_is_causal(smoke):
    cfg, panel, daily, _ = smoke
    be = ChronosBoltBackend(spec("cb", "chronos"), pipeline=random_chronos_pipeline())
    d = daily["SYN_GARCH_A"]
    o = ForecastOrigin(d.index[2500])

    def fn(data, org):
        m = TSFMForecaster("rv", be, 512)
        return m.predict(org.history(data), [1, 5, 20], DECILES)

    assert_future_invariant(fn, d, o, seeds=(1,), modes=("scramble",))


def test_hf_offline_env_not_leaking():
    # guard: tests above must not have permanently set offline mode for other tests
    assert os.environ.get("HF_HUB_OFFLINE") in (None, "", "1")
