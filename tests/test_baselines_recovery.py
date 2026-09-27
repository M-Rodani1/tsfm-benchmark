"""Baselines recover known behaviour on synthetic data with known parameters."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tsfm_rc.data.synthetic import (
    GarchSpec,
    HarSpec,
    VolumeSpec,
    garch_expected_variance,
    gk_discretisation_factor,
    har_expected_variance,
    simulate_asset,
    trading_calendar,
    volume_expected_logvol,
)
from tsfm_rc.data.targets import daily_series
from tsfm_rc.models.baselines import (
    ARBIC,
    EWMA,
    GARCH,
    GJRGARCH,
    HAR,
    LGBM,
    HistMean,
    SeasonalNaive,
    ar_bic_select,
    ewma_next_variance,
)

STEPS = 100


def _sim(spec, n_years=12, seed=0, vol=VolumeSpec()):
    dates = trading_calendar("2000-01-03", f"{2000 + n_years}-12-31")
    ohlcv, latent = simulate_asset(spec, vol, dates, np.random.default_rng(seed), steps=STEPS)
    return daily_series(ohlcv), latent


def qlike(y, f):
    return np.mean(y / f - np.log(y / f) - 1)


@pytest.mark.slow
def test_garch_recovers_parameters_and_true_variance():
    spec = GarchSpec(0.05, 0.08, 0.90, mu=0.03)
    daily, latent = _sim(spec, n_years=16, seed=3)
    m = GARCH("rv")
    m.fit(daily)
    mu, omega, alpha, beta, nu = m.params
    assert alpha == pytest.approx(spec.alpha, abs=0.03)
    assert beta == pytest.approx(spec.beta, abs=0.04)
    assert nu > 15  # data are conditionally Gaussian -> heavy-tail parameter drifts large
    # one-step forecasts along the last 250 days vs the true conditional variance
    kappa = gk_discretisation_factor(STEPS)
    preds, truth = [], []
    for i in range(len(daily) - 250, len(daily)):
        h = daily.iloc[: i + 1]
        preds.append(m.predict(h, [1]).point[1])
        truth.append(kappa * latent["sigma2_next"].iloc[i])  # E[GK_{t+1}] = kappa sigma2_{t+1}
    preds, truth = np.array(preds), np.array(truth)
    assert np.corrcoef(preds, truth)[0, 1] > 0.97
    assert np.mean(preds / truth) == pytest.approx(1.0, abs=0.12)


@pytest.mark.slow
def test_gjr_nests_garch_on_symmetric_data():
    spec = GarchSpec(0.05, 0.08, 0.90)
    daily, _ = _sim(spec, n_years=10, seed=4)
    m = GJRGARCH("rv")
    m.fit(daily)
    gamma = m.params[3]
    assert abs(gamma) < 0.05


def test_har_captures_most_attainable_gain_on_har_process():
    """HAR is fitted by OLS on the *noisy* GK proxy (errors in variables), so it cannot
    match the oracle, which sees the latent variance. Observed while building (seeds
    5-7): HAR's QLIKE is 9-22% above the oracle's, the unconditional mean's 58-181%.
    The test claims what matters: HAR closes most of the gap between "no model" and
    the oracle."""
    spec = HarSpec(0.1, 0.35, 0.35, 0.2, shock_sd=0.5)
    daily, latent = _sim(spec, n_years=14, seed=5)
    kappa = gk_discretisation_factor(STEPS)
    split = len(daily) - 300
    m = HAR("rv", horizons=(1, 5))
    m.fit(daily.iloc[:split])
    s2 = latent["sigma2"].to_numpy()
    har_f, orc_f, y = [], [], []
    for i in range(split, len(daily) - 5):
        h = daily.iloc[: i + 1]
        har_f.append(m.predict(h, [5]).point[5])
        orc_f.append(kappa * har_expected_variance(spec, s2[: i + 1], 5).mean())
        y.append(daily["gk"].iloc[i + 1 : i + 6].mean())
    y, har_f, orc_f = map(np.array, (y, har_f, orc_f))
    uncond = np.full_like(y, daily["gk"].iloc[:split].mean())
    assert np.corrcoef(har_f, orc_f)[0, 1] > 0.75
    gap_har = qlike(y, har_f) - qlike(y, orc_f)
    gap_unc = qlike(y, uncond) - qlike(y, orc_f)
    assert gap_unc > 0 and gap_har < 0.5 * gap_unc


def test_ar_bic_selects_true_order():
    rng = np.random.default_rng(0)
    picks = []
    for _rep in range(10):
        e = rng.standard_normal(3000)
        x = np.zeros(3000)
        for t in range(2, 3000):
            x[t] = 0.5 * x[t - 1] - 0.3 * x[t - 2] + e[t]
        p, beta, s2 = ar_bic_select(x, 10)
        picks.append(p)
        if p == 2:
            np.testing.assert_allclose(beta[1:], [0.5, -0.3], atol=0.06)
    assert np.mean(np.array(picks) == 2) >= 0.8
    white = [ar_bic_select(rng.standard_normal(3000), 10)[0] for _ in range(10)]
    assert np.mean(np.array(white) == 0) >= 0.8


def test_ar_bic_rss_trick_matches_direct_ols():
    rng = np.random.default_rng(1)
    x = np.cumsum(rng.standard_normal(500)) * 0.1 + rng.standard_normal(500)
    p, beta, s2 = ar_bic_select(x, 5)
    n = len(x) - 5
    X = np.column_stack([np.ones(n)] + [x[5 - j : len(x) - j] for j in range(1, p + 1)])
    ref, *_ = np.linalg.lstsq(X, x[5:], rcond=None)
    np.testing.assert_allclose(beta, ref, rtol=1e-8, atol=1e-10)


def test_ewma_matches_manual_recursion():
    rng = np.random.default_rng(2)
    r = rng.standard_normal(300)
    s = np.mean(r[:22] ** 2)
    for x in r:
        s = 0.94 * s + 0.06 * x**2
    assert ewma_next_variance(r, 0.94) == pytest.approx(s, rel=1e-12)


def test_ewma_applies_training_window_proxy_alignment():
    idx = pd.bdate_range("2020-01-01", periods=100)
    r = pd.Series(np.random.default_rng(3).standard_normal(100), index=idx)
    h = pd.DataFrame({"r": r, "gk": 0.5 * r**2 + 0.1})
    m = EWMA("rv")
    m.fit(h)
    c = h["gk"].mean() / (h["r"] ** 2).mean()
    assert m.predict(h, [1]).point[1] == pytest.approx(c * ewma_next_variance(r.to_numpy(), 0.94))


def test_hist_mean_and_quantiles():
    idx = pd.bdate_range("2020-01-01", periods=101)
    r = pd.Series(np.arange(101.0) - 50, index=idx)
    m = HistMean("returns")
    m.fit(pd.DataFrame({"r": r}))
    fc = m.predict(None, [1, 5], [0.1, 0.5, 0.9])
    assert fc.point[5] == pytest.approx(0.0)
    np.testing.assert_allclose(fc.quantiles.values[1], [-40, 0, 40])


def test_seasonal_naive_exact_on_pure_weekday_pattern():
    idx = pd.bdate_range("2021-01-04", periods=60)  # Monday start
    pattern = np.array([10.0, 11.0, 12.0, 13.0, 14.0])
    lv = pd.Series(pattern[idx.dayofweek], index=idx)
    h = pd.DataFrame({"logvol_in": lv, "dow": idx.dayofweek})
    fc = SeasonalNaive("volume").predict(h, [1, 5])
    nxt = (idx[-1] + pd.offsets.BDay(1)).dayofweek
    assert fc.point[1] == pattern[nxt]
    assert fc.point[5] == pytest.approx(pattern.mean())


def test_har_volume_and_lgbm_track_volume_oracle():
    vspec = VolumeSpec()
    daily, latent = _sim(GarchSpec(0.02, 0.08, 0.9), n_years=10, seed=6, vol=vspec)
    split = len(daily) - 200
    har = HAR("volume", horizons=(1,))
    har.fit(daily.iloc[:split])
    lg = LGBM("volume", horizons=(1,), params={"n_estimators": 100})
    lg.fit(daily.iloc[:split])
    a, b, o = [], [], []
    for i in range(split, len(daily) - 1):
        h = daily.iloc[: i + 1]
        a.append(har.predict(h, [1]).point[1])
        b.append(lg.predict(h, [1]).point[1])
        fut = daily.index[i + 1 : i + 2]
        o.append(volume_expected_logvol(vspec, latent["vol_fast"].iloc[i], latent["vol_slow"].iloc[i], fut)[0])
    assert np.corrcoef(a, o)[0, 1] > 0.8
    assert np.corrcoef(b, o)[0, 1] > 0.8


def test_ar_bic_iterated_forecast_matches_manual():
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2015-01-01", periods=800)
    x = np.zeros(800)
    for t in range(1, 800):
        x[t] = 0.6 * x[t - 1] + rng.standard_normal()
    h = pd.DataFrame({"logvol_in": x + 15}, index=idx)
    m = ARBIC("volume", pmax=3)
    m.fit(h)
    fc = m.predict(h, [1, 3])
    b = m.beta
    assert m.p == 1
    f1 = b[0] + b[1] * h["logvol_in"].iloc[-1]
    f2 = b[0] + b[1] * f1
    f3 = b[0] + b[1] * f2
    assert fc.point[1] == pytest.approx(f1)
    assert fc.point[3] == pytest.approx((f1 + f2 + f3) / 3)


def test_garch_expected_variance_consistency_with_arch():
    """Our GARCH wrapper's multi-step path equals the analytic formula with fitted params."""
    spec = GarchSpec(0.05, 0.08, 0.90)
    daily, _ = _sim(spec, n_years=8, seed=8)
    m = GARCH("rv")
    m.fit(daily)
    mu, omega, alpha, beta, nu = m.params
    fc = m.predict(daily, [1, 20])
    from tsfm_rc.models.baselines import proxy_alignment

    c = proxy_alignment(daily)
    s1 = fc.point[1] / c
    est = GarchSpec(omega, alpha, beta)
    path = garch_expected_variance(est, np.array(s1), 20)
    assert fc.point[20] / c == pytest.approx(path.mean(), rel=1e-6)
