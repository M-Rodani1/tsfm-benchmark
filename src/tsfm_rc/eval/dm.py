"""Diebold-Mariano test with Newey-West HAC variance and the HLN small-sample correction.

For a loss differential d_t = L1_t - L2_t (t = 1..T):

    DM   = dbar / sqrt(Omega / T)
    Omega = gamma_0 + 2 sum_{k=1}^{L} w_k gamma_k,   w_k = 1 - k/(L+1) (Bartlett)
                                                      w_k = 1          (rectangular, R's dm.test)
    HLN: DM* = DM * sqrt((T + 1 - 2k + k(k-1)/T) / T),  p-value from t_{T-1}   (k = h_eff)

Kernel and lag (PREREGISTRATION.md section 7 as amended by A2). q_h = ceil(h / stride) - 1
is the MA order induced by overlapping targets and h_eff = q_h + 1 the horizon in sampling
units.

- no overlap (q_h = 0): Bartlett kernel, L = floor(4 (T/100)^(2/9)) (Newey-West 1994 rule);
- overlap (q_h > 0):    rectangular kernel, L = q_h (Diebold-Mariano 1995 / HLN 1997).

Amendment A2 replaced "Bartlett with L = max(q_h, NW)" for the overlap case after a Monte
Carlo showed 9-12% rejections at nominal 5% for 20-day targets sampled every 5 days, versus
5-8% for the rectangular kernel (tests/test_stats.py reproduces both).

A non-positive variance (possible with the rectangular kernel) falls back to the Bartlett
kernel with the same lag, then to lag 0, and the result is flagged; never silently ignored.

Amendment A4 (primary family and stride-1 origins only): ``method="kv_b1"`` uses the
Kiefer-Vogelsang fixed-b test (Bartlett kernel, bandwidth M = T, no HLN factor) with its own
limiting distribution (:mod:`tsfm_rc.eval.fixedb`). Chosen by the size simulation in
DECISIONS D-039; the variance is a sum of squares and cannot be negative.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
from scipy import stats

from tsfm_rc.eval.fixedb import kv_long_run_variance, kv_pvalue


def autocov(d: np.ndarray, k: int) -> float:
    d = np.asarray(d, float)
    dm = d - d.mean()
    T = len(d)
    return float(np.dot(dm[k:], dm[: T - k]) / T)


def long_run_variance(d: np.ndarray, lag: int, kernel: str = "bartlett") -> float:
    omega = autocov(d, 0)
    for k in range(1, lag + 1):
        w = 1.0 - k / (lag + 1.0) if kernel == "bartlett" else 1.0
        omega += 2.0 * w * autocov(d, k)
    return omega


def overlap_order(h: int, stride: int) -> int:
    """q_h = ceil(h/stride) - 1: number of later origins whose target overlaps this one's."""
    return max(0, math.ceil(h / stride) - 1)


def nw_lag(T: int, q_h: int) -> int:
    return max(q_h, int(math.floor(4.0 * (T / 100.0) ** (2.0 / 9.0))))


@dataclass
class DMResult:
    stat: float
    pvalue: float
    mean_diff: float
    se: float
    T: int
    lag: int
    h_eff: int
    flag: str = ""
    method: str = "hln"

    def as_dict(self) -> dict:
        return asdict(self)


def h_eff_for(h: int, stride: int) -> int:
    """Horizon in sampling units: number of consecutive origins whose targets overlap, + 1."""
    return overlap_order(h, stride) + 1


def default_kernel_and_lag(T: int, h_eff: int) -> tuple[str, int]:
    """Pre-registered rule as amended by A2 (see module docstring)."""
    q_h = h_eff - 1
    if q_h > 0:
        return "rectangular", q_h
    return "bartlett", nw_lag(T, 0)


def dm_test(
    d: np.ndarray,
    *,
    h_eff: int = 1,
    lag: int | None = None,
    kernel: str | None = None,
    hln: bool = True,
    method: str = "hln",
) -> DMResult:
    """Two-sided DM test of E[d] = 0. Negative mean = first model has lower loss.

    ``method="hln"`` (default): DM-HLN with the A2 kernel/lag rule; ``kernel``/``lag`` may be
    passed explicitly only to reproduce other conventions (e.g. R's ``dm.test``: rectangular,
    lag h-1). ``method="kv_b1"``: Kiefer-Vogelsang fixed-b test, bandwidth T (amendment A4).
    """
    if method not in ("hln", "kv_b1"):
        raise ValueError(f"unknown DM method {method!r}")
    d = np.asarray(d, float)
    d = d[np.isfinite(d)]
    T = len(d)
    if T < 3:
        return DMResult(np.nan, np.nan, float(np.mean(d)) if T else np.nan, np.nan, T, 0, h_eff, "too_few_obs", method)
    if method == "kv_b1":
        dbar = float(d.mean())
        omega = kv_long_run_variance(d)
        if omega <= 0:
            return DMResult(np.nan, np.nan, dbar, 0.0, T, T - 1, h_eff, "zero_variance", method)
        se = math.sqrt(omega / T)
        stat = dbar / se
        return DMResult(float(stat), kv_pvalue(stat), dbar, se, T, T - 1, h_eff, "", method)
    k_def, l_def = default_kernel_and_lag(T, h_eff)
    kernel = kernel or k_def
    L = l_def if lag is None else int(lag)
    flag = ""
    omega = long_run_variance(d, L, kernel)
    if omega <= 0 and kernel == "rectangular":
        flag = "nonpositive_variance_bartlett_fallback"
        kernel = "bartlett"
        omega = long_run_variance(d, L, kernel)
    if omega <= 0 and L > 0:
        flag = "nonpositive_variance_lag_reduced_to_0"
        L = 0
        omega = long_run_variance(d, L, kernel)
    dbar = float(d.mean())
    if omega <= 0:
        return DMResult(np.nan, np.nan, dbar, 0.0, T, L, h_eff, "zero_variance")
    se = math.sqrt(omega / T)
    stat = dbar / se
    if hln:
        k = h_eff
        adj = (T + 1 - 2 * k + k * (k - 1) / T) / T
        stat *= math.sqrt(max(adj, 0.0))
    pvalue = float(2.0 * stats.t.sf(abs(stat), df=T - 1))
    return DMResult(float(stat), pvalue, dbar, se, T, L, h_eff, flag)
