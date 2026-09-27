"""Every baseline, for every target it supports, must be future-invariant.

Two scenarios per model:
1. fit and predict at the same origin t (the common case);
2. fit at an earlier origin A, predict at t with frozen parameters (the re-fit schedule).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tsfm_rc.config import BASELINES_BY_TARGET, load_config
from tsfm_rc.data.provider import FixtureProvider
from tsfm_rc.data.targets import daily_series
from tsfm_rc.leakage import assert_future_invariant
from tsfm_rc.models.registry import make_baseline
from tsfm_rc.origin import ForecastOrigin
from tsfm_rc.paths import FIXTURE_DIR

CFG = load_config("configs/smoke.yaml")
CFG = CFG.model_copy(update={"models": CFG.models.model_copy(update={"lgbm": CFG.models.lgbm.model_copy(update={"n_estimators": 20})})})
LEVELS = CFG.stats.quantile_levels
HORIZONS = [1, 5, 20]

PAIRS = [(name, kind) for kind, names in BASELINES_BY_TARGET.items() for name in names]


@pytest.fixture(scope="module")
def daily() -> pd.DataFrame:
    raw = FixtureProvider(FIXTURE_DIR / "synthetic_ohlcv.csv").fetch("SYN_HAR_A", "2010-01-01", "2016-12-31")
    return daily_series(raw)


def _as_ohlcv_free(d: pd.DataFrame) -> pd.DataFrame:
    return d


@pytest.mark.parametrize("name,kind", PAIRS, ids=[f"{n}-{k}" for n, k in PAIRS])
def test_fit_predict_same_origin_is_causal(daily, name, kind):
    origin = ForecastOrigin(daily.index[1200])

    def fn(data, o):
        m = make_baseline(name, kind, CFG, seed=1)
        h = o.history(data)
        m.fit(h)
        return m.predict(h, HORIZONS, LEVELS)

    # only perturb columns that exist in the daily frame; gk must stay positive
    assert_future_invariant(fn, daily, origin, seeds=(1,), modes=("scramble",))


@pytest.mark.parametrize("name,kind", PAIRS, ids=[f"{n}-{k}" for n, k in PAIRS])
def test_frozen_parameters_predict_is_causal(daily, name, kind):
    fit_origin = ForecastOrigin(daily.index[1100])
    origin = ForecastOrigin(daily.index[1250])

    def fn(data, o):
        m = make_baseline(name, kind, CFG, seed=1)
        m.fit(fit_origin.history(data))
        return m.predict(o.history(data), HORIZONS, LEVELS)

    assert_future_invariant(fn, daily, origin, seeds=(2,), modes=("shock",))


@pytest.mark.parametrize("name,kind", PAIRS, ids=[f"{n}-{k}" for n, k in PAIRS])
def test_forecasts_finite_and_quantiles_ordered(daily, name, kind):
    m = make_baseline(name, kind, CFG, seed=0)
    h = daily.iloc[:1500]
    m.fit(h)
    fc = m.predict(h, HORIZONS, LEVELS)
    pts = np.array([fc.point[x] for x in HORIZONS])
    assert np.isfinite(pts).all()
    if kind == "rv":
        assert (pts > 0).all()
    if fc.quantiles is not None:
        q = fc.quantiles.values[1]
        assert len(q) == len(LEVELS) and np.all(np.diff(q) >= 0)
