"""The NumPy/SciPy GARCH(1,1)-t used by the browser lessons reproduces ``arch``.

The lesson website runs Python in the browser (Pyodide), where ``arch`` is not available.
Lesson 04 therefore fits GARCH with :mod:`tsfm_rc.models.garch_np`. These tests prove, on
the committed fixtures, that it is the same estimator as the study's ``arch`` model:
identical log-likelihood at the same parameters, and the same fitted parameters.
"""

from __future__ import annotations

import numpy as np
import pytest

from tsfm_rc.data.provider import FixtureProvider
from tsfm_rc.data.targets import daily_series
from tsfm_rc.models.garch_np import backcast, fit_garch11_t, garch11_variance, loglik
from tsfm_rc.paths import FIXTURE_DIR

TICKERS = ["SYN_GARCH_A", "SYN_GARCH_B", "SYN_HAR_A", "SYN_QUIRKS"]


def _returns(ticker: str) -> np.ndarray:
    raw = FixtureProvider(FIXTURE_DIR / "synthetic_ohlcv.csv").fetch(ticker, "2010-01-01", "2026-12-31")
    return daily_series(raw)["r"].dropna().to_numpy()


def _arch(r: np.ndarray):
    from arch import arch_model

    return arch_model(r, mean="Constant", vol="GARCH", p=1, q=1, dist="t", rescale=False)


@pytest.mark.parametrize("ticker", TICKERS)
def test_variance_path_and_loglik_equal_arch_at_fixed_parameters(ticker):
    r = _returns(ticker)[:1500]
    params = np.array([0.02, 0.03, 0.07, 0.9, 9.0])
    fixed = _arch(r).fix(params)
    s2_arch = np.asarray(fixed.conditional_volatility) ** 2
    bc = backcast(r - r.mean())  # arch: backcast from residuals around the sample mean
    np.testing.assert_allclose(garch11_variance(r - params[0], *params[1:4], bc), s2_arch, rtol=1e-10)
    assert loglik(params, r) == pytest.approx(fixed.loglikelihood, rel=1e-10)


@pytest.mark.parametrize("ticker", TICKERS)
@pytest.mark.parametrize("n", [1200, None])
def test_fitted_parameters_match_arch(ticker, n):
    r = _returns(ticker)
    r = r[:n] if n else r
    ref = _arch(r).fit(disp="off", options={"maxiter": 1000})
    ours = fit_garch11_t(r)
    assert ours.converged
    ap = ref.params.to_numpy()
    # same optimum: our likelihood is at least as high as arch's (up to optimiser tolerance)
    assert ours.loglik >= ref.loglikelihood - 0.01
    np.testing.assert_allclose(ours.params[:4], ap[:4], atol=2e-3)  # mu, omega, alpha, beta
    # nu is weakly identified when large (flat likelihood); require agreement only when it matters
    if ap[4] < 30:
        assert ours.nu == pytest.approx(ap[4], rel=0.05)
