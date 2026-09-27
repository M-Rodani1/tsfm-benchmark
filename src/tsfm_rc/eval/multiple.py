"""Multiple-comparison control: Holm (1979) step-down adjustment of p-values."""

from __future__ import annotations

import numpy as np


def holm(pvalues, alpha: float = 0.05) -> tuple[np.ndarray, np.ndarray]:
    """Holm-adjusted p-values and rejections (family-wise error rate <= alpha).

    Sort p ascending; adjusted p_(i) = max_{j <= i} min(1, (m - j + 1) p_(j)).
    NaN p-values (e.g. UNAVAILABLE models) are left NaN and do not count towards m.
    """
    p = np.asarray(pvalues, float)
    adj = np.full_like(p, np.nan)
    ok = np.isfinite(p)
    m = int(ok.sum())
    if m == 0:
        return adj, np.zeros_like(p, dtype=bool)
    idx = np.flatnonzero(ok)
    order = idx[np.argsort(p[idx], kind="stable")]
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[i]))
        adj[i] = running
    return adj, np.where(ok, adj <= alpha, False)
