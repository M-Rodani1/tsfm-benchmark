"""Statistical routines vs reference implementations, closed forms and Monte Carlo size."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from tsfm_rc.eval.bootstrap import block_length, stationary_bootstrap_indices
from tsfm_rc.eval.dm import dm_test, h_eff_for, long_run_variance, nw_lag, overlap_order
from tsfm_rc.eval.fixedb import kv_critical_value, kv_long_run_variance, kv_pvalue
from tsfm_rc.eval.mcs import model_confidence_set
from tsfm_rc.eval.metrics import (
    crps_from_quantiles,
    directional_hit,
    oos_r2,
    pinball,
    qlike,
    squared_error,
)
from tsfm_rc.eval.multiple import holm


# ============================================================ metrics
def test_qlike_properties_and_known_value():
    assert qlike([2.0], [2.0])[0] == 0.0
    assert qlike([2.0], [1.0])[0] == pytest.approx(2 - math.log(2) - 1)
    assert np.isnan(qlike([1.0], [0.0])[0]) and np.isnan(qlike([-1.0], [1.0])[0])
    # E[QLIKE(y, f)] is minimised at f = E[y] (Patton 2011): check on a gamma proxy
    y = np.random.default_rng(0).gamma(2.0, 1.5, 200_000)  # mean 3
    grid = np.linspace(2.0, 4.0, 81)
    best = grid[np.argmin([qlike(y, np.full_like(y, f)).mean() for f in grid])]
    assert best == pytest.approx(3.0, abs=0.05)


def test_pinball_and_crps_normal_closed_form():
    assert pinball([1.0], [0.0], 0.9)[0] == pytest.approx(0.9)
    assert pinball([-1.0], [0.0], 0.9)[0] == pytest.approx(0.1)
    # CRPS of N(mu, s) at y (Gneiting & Raftery 2007): s [z(2Phi(z)-1) + 2phi(z) - 1/sqrt(pi)]
    mu, s, y = 0.3, 1.7, np.array([1.1, -2.0, 0.3])
    z = (y - mu) / s
    exact = s * (z * (2 * stats.norm.cdf(z) - 1) + 2 * stats.norm.pdf(z) - 1 / np.sqrt(np.pi))
    K = 999
    levels = np.arange(1, K + 1) / (K + 1)
    Q = np.tile(mu + s * stats.norm.ppf(levels), (3, 1))
    np.testing.assert_allclose(crps_from_quantiles(y, Q, levels), exact, rtol=2e-3)
    # the 9-decile version used in the study is a coarse approximation: observed 5-10% above
    # the exact CRPS for a normal forecast (same for every model), ordering preserved
    dec = np.arange(1, 10) / 10
    approx = crps_from_quantiles(y, np.tile(mu + s * stats.norm.ppf(dec), (3, 1)), dec)
    assert np.all(np.abs(approx / exact - 1) < 0.12)
    assert np.argsort(approx).tolist() == np.argsort(exact).tolist()


def test_directional_and_oos_r2():
    np.testing.assert_array_equal(directional_hit([1, -1, 2], [0.5, 0.5, 0.0]), [1.0, 0.0, np.nan])
    y = np.array([1.0, 2.0, 3.0])
    assert oos_r2(y, y, np.zeros(3)) == 1.0
    assert oos_r2(y, np.zeros(3), np.zeros(3)) == 0.0
    assert squared_error([1], [3])[0] == 4


# ============================================================ HAC / DM
def test_long_run_variance_matches_statsmodels_hac():
    import statsmodels.api as sm

    rng = np.random.default_rng(1)
    e = rng.standard_normal(600)
    d = e[1:] + 0.6 * e[:-1] + 0.2  # MA(1) with mean
    for L in (0, 1, 3, 8):
        res = sm.OLS(d, np.ones_like(d)).fit(cov_type="HAC", cov_kwds={"maxlags": L, "use_correction": False})
        sm_var_of_mean = float(res.cov_params()[0, 0])
        assert long_run_variance(d, L) / len(d) == pytest.approx(sm_var_of_mean, rel=1e-10)


@pytest.mark.parametrize("h", [1, 2, 4])
@pytest.mark.parametrize("kernel,ref_est", [("rectangular", "acf"), ("bartlett", "bartlett")])
def test_dm_matches_reference_package(h, kernel, ref_est):
    """dieboldmariano 1.1.0 (PyPI) implements DM-HLN with lag h-1 (acf = R's dm.test)."""
    from dieboldmariano import dm_test as ref_dm

    rng = np.random.default_rng(10 + h)
    y = rng.standard_normal(300)
    p1 = y + rng.standard_normal(300) * 0.9
    p2 = y + rng.standard_normal(300) * 1.1
    stat_ref, p_ref = ref_dm(list(y), list(p1), list(p2), h=h, harvey_correction=True, variance_estimator=ref_est)
    d = (y - p1) ** 2 - (y - p2) ** 2
    ours = dm_test(d, h_eff=h, lag=h - 1, kernel=kernel, hln=True)
    assert ours.stat == pytest.approx(stat_ref, rel=1e-9)
    assert ours.pvalue == pytest.approx(p_ref, rel=1e-6)


def test_dm_hln_matches_hand_formula():
    d = np.array([0.5, -0.2, 0.3, 0.9, -0.4, 0.1, 0.6, 0.2])
    T, k = len(d), 2
    g0 = np.mean((d - d.mean()) ** 2)
    g1 = np.sum((d[1:] - d.mean()) * (d[:-1] - d.mean())) / T
    omega = g0 + 2 * 0.5 * g1  # Bartlett weight for lag 1 of L = 1 is 1 - 1/2
    dm = d.mean() / math.sqrt(omega / T)
    dm_hln = dm * math.sqrt((T + 1 - 2 * k + k * (k - 1) / T) / T)
    r = dm_test(d, h_eff=2, lag=1, kernel="bartlett")
    assert r.stat == pytest.approx(dm_hln)
    assert r.pvalue == pytest.approx(2 * stats.t.sf(abs(dm_hln), T - 1))
    # default for overlapping targets (h_eff > 1): rectangular kernel with lag q_h = 1
    omega_rect = g0 + 2 * g1
    expected = d.mean() / math.sqrt(omega_rect / T) * math.sqrt((T + 1 - 2 * k + k * (k - 1) / T) / T)
    assert dm_test(d, h_eff=2).stat == pytest.approx(expected)


def test_lag_rules():
    assert [overlap_order(h, 5) for h in (1, 5, 20)] == [0, 0, 3]
    assert overlap_order(20, 10) == 1
    assert nw_lag(100, 0) == 4 and nw_lag(590, 0) == 5 and nw_lag(50, 3) == 3


def test_dm_flags_degenerate_inputs():
    assert dm_test(np.zeros(50)).flag == "zero_variance"
    assert dm_test(np.array([1.0, 2.0])).flag == "too_few_obs"


def _overlap_sums(rng, T, phi, h=20, stride=5):
    """Loss differentials of 20-day targets sampled every 5 days: sums of daily AR(1)
    contributions over overlapping windows (the study's h=20 design under H0)."""
    n = stride * T + h
    e = rng.standard_normal(n + 200)
    u = np.zeros_like(e)
    for t in range(1, len(e)):
        u[t] = phi * u[t - 1] + e[t]
    c = np.cumsum(np.r_[0, u[200:]])
    s = np.arange(0, stride * T, stride)
    return c[s + h] - c[s]


@pytest.mark.slow
@pytest.mark.parametrize("T", [150, 590])
def test_dm_size_under_overlap_amended_rule(T):
    """Default (amended, A2) rule for h=20/stride 5 keeps size near 5%; the original
    pre-registered Bartlett rule over-rejects. This is the evidence for amendment A2."""
    rng = np.random.default_rng(42)
    R = 1500
    rej_new = rej_old = 0
    for _ in range(R):
        d = _overlap_sums(rng, T, 0.3)
        rej_new += dm_test(d, h_eff=4).pvalue < 0.05
        rej_old += dm_test(d, h_eff=4, kernel="bartlett", lag=nw_lag(T, 3)).pvalue < 0.05
    assert 0.035 <= rej_new / R <= 0.075, rej_new / R
    assert rej_old / R > 0.08, rej_old / R  # documents the flaw that motivated A2


@pytest.mark.slow
def test_dm_size_no_overlap():
    rng = np.random.default_rng(43)
    T, R = 300, 2000
    rej = sum(dm_test(rng.standard_normal(T)).pvalue < 0.05 for _ in range(R))
    assert 0.035 <= rej / R <= 0.065, rej / R


# ============================================================ amendment A4: fixed-b test, stride 1
def test_kv_variance_is_bartlett_with_bandwidth_T():
    rng = np.random.default_rng(0)
    for T in (5, 57, 300):
        d = rng.standard_normal(T) + 0.3
        assert kv_long_run_variance(d) == pytest.approx(long_run_variance(d, T - 1, "bartlett"), rel=1e-12)


def test_kv_pvalues_reproduce_published_critical_values():
    """Kiefer & Vogelsang (2002), Bartlett kernel, M = T: right-tail 90/95/97.5/99% critical
    values 2.740 / 3.764 / 4.771 / 6.090, i.e. two-sided p = 0.20 / 0.10 / 0.05 / 0.02."""
    for c, p in [(2.740, 0.20), (3.764, 0.10), (4.771, 0.05), (6.090, 0.02)]:
        assert kv_pvalue(c) == pytest.approx(p, abs=2e-4)
        assert kv_pvalue(-c) == kv_pvalue(c)
    assert kv_critical_value(0.05) == pytest.approx(4.771, abs=1e-3)
    assert kv_pvalue(0.0) == 1.0 and kv_pvalue(50.0) < 1e-6


def test_kv_limit_distribution_by_simulation():
    """Independent check of the closed form: simulate the statistic under i.i.d. data (T = 400)."""
    rng = np.random.default_rng(11)
    D = rng.standard_normal((20000, 400))
    dbar = D.mean(1)
    S = np.cumsum(D - dbar[:, None], axis=1)
    t = dbar / np.sqrt(2.0 * (S**2).sum(1) / 400**2 / 400)
    for c in (2.740, 4.771):
        assert np.mean(np.abs(t) > c) == pytest.approx(kv_pvalue(c), abs=0.008)


def test_dm_test_kv_method():
    rng = np.random.default_rng(4)
    d = rng.standard_normal(250) + 0.1
    r = dm_test(d, h_eff=20, method="kv_b1")
    assert r.method == "kv_b1" and r.lag == 249 and r.h_eff == 20
    assert r.stat == pytest.approx(d.mean() / math.sqrt(kv_long_run_variance(d) / 250))
    assert r.pvalue == pytest.approx(kv_pvalue(r.stat))
    assert dm_test(np.ones(40), method="kv_b1").flag == "zero_variance"  # variance >= 0 always; = 0 only if constant
    with pytest.raises(ValueError):
        dm_test(d, method="bogus")
    assert [h_eff_for(h, 1) for h in (1, 5, 20)] == [1, 5, 20]
    assert [h_eff_for(h, 5) for h in (1, 5, 20)] == [1, 1, 4]


@pytest.mark.slow
def test_a4_size_grid_stride1():
    """The A4 simulation (DECISIONS D-039) re-run with fewer replications: stride-1 origins,
    T in {100, 250, 450}, h in {1, 5, 20}, four null DGPs. The fixed-b test must again have
    the smallest worst-case size distortion, and its sizes must agree with the documented
    run (KV_SIM_MAX_SIZE) within Monte Carlo error."""
    from tsfm_rc.eval.size_study import KV_SIM_MAX_SIZE, size_grid, summarise

    R = 1500
    g = size_grid(R=R, seed=7)
    summ = summarise(g)
    assert summ.iloc[0]["test"] == "kv_b1", summ
    assert summ.set_index("test").loc["kv_b1", "max_size"] < 0.14
    assert summ.set_index("test").loc["rect", "max_size"] > 0.25  # lag 0 at h = 1 ignores persistence
    worst = g.groupby(["T", "h"])["kv_b1"].max()
    for (T, h), documented in KV_SIM_MAX_SIZE.items():
        se = math.sqrt(documented * (1 - documented) / R)
        assert abs(worst[(T, h)] - documented) < 4.5 * se + 0.01, (T, h, worst[(T, h)], documented)


def test_dm_power_against_shift():
    rng = np.random.default_rng(3)
    d = rng.standard_normal(400) + 0.4
    r = dm_test(d)
    assert r.pvalue < 1e-6 and r.stat > 0


# ============================================================ Holm
def test_holm_matches_statsmodels():
    from statsmodels.stats.multitest import multipletests

    rng = np.random.default_rng(5)
    p = np.concatenate([rng.uniform(0, 0.02, 5), rng.uniform(0, 1, 20)])
    adj, rej = holm(p, 0.05)
    rej_ref, adj_ref, *_ = multipletests(p, alpha=0.05, method="holm")
    np.testing.assert_allclose(adj, adj_ref)
    np.testing.assert_array_equal(rej, rej_ref)


def test_holm_worked_example_and_nans():
    # Holm (1979)-style example: p = 0.01, 0.04, 0.03, 0.005 with m = 4
    adj, rej = holm([0.01, 0.04, 0.03, 0.005], 0.05)
    np.testing.assert_allclose(adj, [0.03, 0.06, 0.06, 0.02])
    assert rej.tolist() == [True, False, False, True]
    adj, rej = holm([0.01, np.nan, 0.02])
    assert np.isnan(adj[1]) and not rej[1]
    np.testing.assert_allclose(adj[[0, 2]], [0.02, 0.02])


# ============================================================ bootstrap and MCS
def test_stationary_bootstrap_properties():
    rng = np.random.default_rng(0)
    idx = stationary_bootstrap_indices(500, 200, 10.0, rng)
    assert idx.shape == (200, 500) and idx.min() >= 0 and idx.max() < 500
    starts = (np.diff(idx, axis=1) != 1) & ~((idx[:, :-1] == 499) & (idx[:, 1:] == 0))
    mean_block = 1.0 / starts.mean()
    assert mean_block == pytest.approx(10.0, rel=0.1)
    np.testing.assert_array_equal(idx, stationary_bootstrap_indices(500, 200, 10.0, np.random.default_rng(0)))
    assert block_length(590, 1) == 9 and block_length(50, 4) == 8


@pytest.mark.parametrize("statistic,arch_method", [("Tmax", "max"), ("TR", "R")])
def test_mcs_reproduces_arch_exactly(statistic, arch_method):
    from arch.bootstrap import MCS

    rng = np.random.default_rng(7)
    T = 250
    base = rng.standard_normal((T, 1)) ** 2
    losses = pd.DataFrame(
        base + np.column_stack([rng.standard_normal(T) * 0.3 + mu for mu in (0.0, 0.02, 0.05, 0.3, 0.6)]) ** 2,
        columns=["a", "b", "c", "d", "e"],
    )
    ref = MCS(losses, size=0.10, reps=500, block_size=8, method=arch_method, bootstrap="stationary", seed=11)
    ref.compute()
    indices = np.stack(ref._bootstrap_indices)
    ours = model_confidence_set(losses, 0.10, statistic=statistic, indices=indices)
    ref_p = ref.pvalues["Pvalue"]
    for m in losses.columns:
        assert ours.pvalues[m] == pytest.approx(ref_p[m], abs=1e-12), (m, ours.pvalues[m], ref_p[m])
    assert sorted(ours.included) == sorted(ref.included)


def test_mcs_clear_cut_case():
    rng = np.random.default_rng(1)
    T = 400
    noise = rng.standard_normal((T, 3)) * 0.2
    losses = np.column_stack([1.0 + noise[:, 0], 1.0 + noise[:, 1], 3.0 + noise[:, 2]])
    res = model_confidence_set(losses, 0.10, B=500, block=5, rng=np.random.default_rng(2), names=["good1", "good2", "bad"])
    assert "bad" not in res.included and {"good1", "good2"} <= set(res.included)
    assert res.pvalues["bad"] < 0.01
