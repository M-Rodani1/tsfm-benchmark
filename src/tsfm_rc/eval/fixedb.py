"""Kiefer–Vogelsang fixed-b test with bandwidth equal to the sample size (amendment A4).

For a loss differential d_t (t = 1..T) with partial sums S_t = sum_{j<=t} (d_j - dbar), the
Bartlett long-run variance with bandwidth M = T is

    Omega_KV = gamma_0 + 2 sum_{k=1}^{T-1} (1 - k/T) gamma_k = 2 T^{-2} sum_t S_t^2

(identical, checked in tests/test_stats.py). The statistic t = dbar / sqrt(Omega_KV / T) is
not asymptotically normal. Its limit is (Kiefer & Vogelsang 2002, Econometrica 70:2093)

    t*  =  W(1) / sqrt(2 Q),     Q = int_0^1 B(r)^2 dr,

with W a Brownian motion and B its Brownian bridge, independent of W(1). Two-sided p-values
are computed exactly (to quadrature precision, no simulation) from

    P(|t*| > c) = E[2 Phi(-c sqrt(2Q))] = (2/pi) int_0^{pi/2} L(c^2 / sin^2 theta) d theta,

using Craig's formula for the normal tail and the Laplace transform of Q for the Brownian
bridge, L(s) = E[exp(-sQ)] = (sqrt(2s) / sinh sqrt(2s))^{1/2}. This reproduces the published
critical values 2.740 / 3.764 / 4.771 / 6.090 (right-tail 90 / 95 / 97.5 / 99%).

The variance is a sum of squares, so it is never negative; it is zero only when every d_t is
equal, in which case the test is not defined (flagged "zero_variance", p = NaN).
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from scipy import integrate, optimize


def kv_long_run_variance(d: np.ndarray) -> float:
    """Bartlett long-run variance with bandwidth M = T, via the partial-sum identity."""
    d = np.asarray(d, float)
    T = len(d)
    S = np.cumsum(d - d.mean())
    return float(2.0 * np.dot(S, S) / T**2)


def _log_laplace_bridge(s: float) -> float:
    """log E[exp(-s Q)] for Q = int_0^1 B(r)^2 dr, B a Brownian bridge."""
    x = math.sqrt(2.0 * s)
    if x < 1e-8:
        return 0.0
    log_sinh = x + math.log1p(-math.exp(-2.0 * x)) - math.log(2.0)
    return 0.5 * (math.log(x) - log_sinh)


@lru_cache(maxsize=4096)
def _pvalue_cached(c: float) -> float:
    if c == 0.0:
        return 1.0

    def f(theta: float) -> float:
        s = math.sin(theta)
        if s <= 0.0:
            return 0.0
        return math.exp(_log_laplace_bridge(c * c / (s * s)))

    val, _ = integrate.quad(f, 0.0, math.pi / 2.0, limit=200, epsabs=1e-14, epsrel=1e-10)
    return float(min(1.0, max(0.0, 2.0 / math.pi * val)))


def kv_pvalue(stat: float) -> float:
    """Two-sided p-value P(|t*| > |stat|) under the KV (b = 1, Bartlett) limit."""
    if not np.isfinite(stat):
        return float("nan")
    return _pvalue_cached(round(abs(float(stat)), 12))


def kv_critical_value(alpha: float = 0.05) -> float:
    """Two-sided critical value c with P(|t*| > c) = alpha."""
    return float(optimize.brentq(lambda c: kv_pvalue(c) - alpha, 1e-6, 200.0, xtol=1e-12))
