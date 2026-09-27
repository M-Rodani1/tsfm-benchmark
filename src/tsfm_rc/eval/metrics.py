"""Loss functions and summary metrics (PREREGISTRATION.md section 6).

All losses are element-wise, so they can be averaged over time, over assets, or turned
into loss *differentials* for Diebold-Mariano tests.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def squared_error(y, f) -> np.ndarray:
    return (np.asarray(y, float) - np.asarray(f, float)) ** 2


def absolute_error(y, f) -> np.ndarray:
    return np.abs(np.asarray(y, float) - np.asarray(f, float))


def qlike(y, f) -> np.ndarray:
    """Patton (2011) QLIKE in its normalised form: y/f - ln(y/f) - 1 >= 0, 0 iff f = y.

    ``y`` is the variance proxy, ``f`` the variance forecast (both > 0). Its expectation is
    minimised at f = E[y], and rankings are robust to noise in a conditionally unbiased proxy.
    Non-positive inputs give NaN (never silently clipped).
    """
    y = np.asarray(y, float)
    f = np.asarray(f, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = y / f
        out = ratio - np.log(ratio) - 1.0
    return np.where((y > 0) & (f > 0), out, np.nan)


def pinball(y, q, tau: float) -> np.ndarray:
    """Quantile (pinball) loss: (tau - 1{y < q}) (y - q)."""
    y = np.asarray(y, float)
    q = np.asarray(q, float)
    return (tau - (y < q)) * (y - q)


def crps_from_quantiles(y, Q, levels: Sequence[float]) -> np.ndarray:
    """CRPS approximated from K quantiles: (2/K) sum_k pinball_{tau_k}.

    CRPS = 2 * integral_0^1 pinball_tau d tau; with K equally spaced interior levels this is
    the midpoint rule. With the nine deciles it ignores the tails beyond 10%/90% (DECISIONS
    D-012), identically for every model, so it is a proper-scoring-rule approximation
    suitable for *comparisons*, not an exact CRPS.
    """
    Q = np.asarray(Q, float)
    y = np.asarray(y, float)
    levels = np.asarray(levels, float)
    loss = (levels[None, :] - (y[:, None] < Q)) * (y[:, None] - Q)
    return 2.0 * loss.mean(axis=1)


def directional_hit(y, f) -> np.ndarray:
    """1 if sign(f) == sign(y), 0 otherwise; NaN when the forecast is exactly 0 (no call)."""
    y = np.asarray(y, float)
    f = np.asarray(f, float)
    return np.where(f == 0, np.nan, (np.sign(f) == np.sign(y)).astype(float))


def oos_r2(y, f, f_bench) -> float:
    """Campbell-Thompson out-of-sample R^2: 1 - SSE(model) / SSE(benchmark)."""
    y, f, b = (np.asarray(a, float) for a in (y, f, f_bench))
    ok = np.isfinite(y) & np.isfinite(f) & np.isfinite(b)
    den = np.sum((y[ok] - b[ok]) ** 2)
    return float(1.0 - np.sum((y[ok] - f[ok]) ** 2) / den) if den > 0 else float("nan")


LOSSES = {"mse": squared_error, "mae": absolute_error, "qlike": qlike}

# Pre-registered primary loss per target
PRIMARY_LOSS = {"returns": "mse", "rv": "qlike", "volume": "mse"}
LOSSES_BY_TARGET = {"returns": ("mse", "mae"), "rv": ("qlike", "mse", "mae"), "volume": ("mse", "mae")}
