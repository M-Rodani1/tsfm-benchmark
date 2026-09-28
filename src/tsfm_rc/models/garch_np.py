"""GARCH(1,1) with Student-t errors in plain NumPy/SciPy (for the browser lessons).

The study's baselines fit GARCH with the ``arch`` package, which is not available in
Pyodide (the in-browser Python used by the lesson website). This module re-implements the
*same* estimator for the lessons only:

- constant mean mu, residuals eps_t = r_t - mu;
- variance recursion sigma2_t = omega + alpha eps_{t-1}^2 + beta sigma2_{t-1}, started from
  arch's backcast for both lagged terms at t = 0: the exponentially weighted mean (weights
  0.94^i) of the first 75 squared residuals *around the sample mean* (arch computes it once
  from its starting values and keeps it fixed while estimating);
- standardised Student-t log-likelihood (arch's ``StudentsT``), maximised with SLSQP under
  omega > 0, alpha, beta >= 0, alpha + beta < 1, 2.05 < nu < 500, from a small grid of
  starting values.

``tests/test_garch_np.py`` checks it against ``arch`` on the committed fixtures (same
log-likelihood at the same parameters; fitted parameters agree to about 1e-3). The research
pipeline itself never uses this module.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
from scipy import optimize
from scipy.special import gammaln


def backcast(eps: np.ndarray) -> float:
    """arch's GARCH backcast: sum_i w_i eps_i^2 over the first min(75, n) residuals, w ~ 0.94^i."""
    eps = np.asarray(eps, float)
    tau = min(75, len(eps))
    w = 0.94 ** np.arange(tau)
    w = w / w.sum()
    return float(np.sum(eps[:tau] ** 2 * w))


def garch11_variance(eps: np.ndarray, omega: float, alpha: float, beta: float, bc: float | None = None) -> np.ndarray:
    """Conditional variances sigma2_t (t = 0..n-1) given data up to t-1 (arch's recursion)."""
    eps = np.asarray(eps, float)
    bc = backcast(eps) if bc is None else bc
    s2 = np.empty(len(eps))
    prev_e2, prev_s2 = bc, bc
    for t in range(len(eps)):
        s2[t] = omega + alpha * prev_e2 + beta * prev_s2
        prev_e2, prev_s2 = eps[t] ** 2, s2[t]
    return s2


def t_loglik(eps: np.ndarray, s2: np.ndarray, nu: float) -> float:
    """Log-likelihood of standardised Student-t errors with variance s2 (arch's StudentsT)."""
    c = gammaln((nu + 1) / 2) - gammaln(nu / 2) - 0.5 * np.log(np.pi * (nu - 2))
    return float(np.sum(c - 0.5 * np.log(s2) - (nu + 1) / 2 * np.log1p(eps**2 / (s2 * (nu - 2)))))


def loglik(params: np.ndarray, r: np.ndarray, bc: float | None = None) -> float:
    mu, omega, alpha, beta, nu = params
    r = np.asarray(r, float)
    bc = backcast(r - r.mean()) if bc is None else bc
    eps = r - mu
    return t_loglik(eps, garch11_variance(eps, omega, alpha, beta, bc), nu)


@dataclass(frozen=True)
class GarchFit:
    mu: float
    omega: float
    alpha: float
    beta: float
    nu: float
    loglik: float
    converged: bool

    @property
    def params(self) -> np.ndarray:
        """Same order as ``arch``: mu, omega, alpha[1], beta[1], nu."""
        return np.array([self.mu, self.omega, self.alpha, self.beta, self.nu])


def fit_garch11_t(r) -> GarchFit:
    """Maximum-likelihood GARCH(1,1)-t with constant mean (percent returns expected)."""
    r = np.asarray(r, float)
    r = r[np.isfinite(r)]
    var = float(np.var(r))
    mu0 = float(np.mean(r))
    bc = backcast(r - mu0)

    def nll(p: np.ndarray) -> float:
        v = -loglik(p, r, bc)
        return v if np.isfinite(v) else 1e12

    bounds = [(-10 * abs(mu0) - 1.0, 10 * abs(mu0) + 1.0), (1e-6 * var, 10 * var), (0.0, 1.0), (0.0, 1.0), (2.05, 500.0)]
    cons = [{"type": "ineq", "fun": lambda p: 1.0 - 1e-6 - p[2] - p[3]}]
    starts = []
    for a in (0.03, 0.08, 0.15):
        for persistence in (0.90, 0.97, 0.995):
            b = persistence - a
            starts.append(np.array([mu0, var * (1 - persistence), a, b, 8.0]))
    best = min(starts, key=nll)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # SLSQP clips steps to the bounds
        res = optimize.minimize(nll, best, method="SLSQP", bounds=bounds, constraints=cons,
                                options={"maxiter": 1000, "ftol": 1e-10})
    p = res.x
    return GarchFit(*map(float, p), loglik=-float(res.fun), converged=bool(res.success))
