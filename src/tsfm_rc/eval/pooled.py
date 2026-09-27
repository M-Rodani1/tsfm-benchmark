"""Pooling across assets (PREREGISTRATION.md section 7, DECISIONS D-014).

1. Normalise each asset's losses by a scale computed from **pre-test data only**
   (targets whose label window ended before the first test origin):
   mse -> variance of the h-step target, mae -> mean absolute deviation,
   qlike -> 1 (already scale-free), crps -> standard deviation.
2. For a comparison (model m vs reference r), pair rows on (asset, origin), take the
   cross-sectional mean of the normalised losses at each origin, and test the time series
   of the pooled differential with DM-HLN. Because assets are averaged *before* the
   long-run variance is estimated, cross-asset correlation is inside that variance.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsfm_rc.data.targets import make_target


def pretest_scales(daily: dict[str, pd.DataFrame], kinds, horizons, test_start) -> pd.DataFrame:
    ts = pd.Timestamp(test_start)
    rows = []
    for t, d in daily.items():
        for kind in kinds:
            for h in horizons:
                y = make_target(d, kind, h)
                label_end = pd.Series(d.index, index=d.index).shift(-h)
                pre = y[(label_end < ts) & y.notna()]
                if len(pre) < 20:
                    continue
                rows += [
                    {"ticker": t, "target": kind, "horizon": h, "loss": "mse", "scale": float(pre.var())},
                    {"ticker": t, "target": kind, "horizon": h, "loss": "mae", "scale": float((pre - pre.mean()).abs().mean())},
                    {"ticker": t, "target": kind, "horizon": h, "loss": "qlike", "scale": 1.0},
                    {"ticker": t, "target": kind, "horizon": h, "loss": "crps", "scale": float(pre.std())},
                ]
    return pd.DataFrame(rows)


def paired_pooled(L: pd.DataFrame, m: str, ref: str, col: str) -> pd.DataFrame:
    """Per-origin cross-sectional means of ``col`` for model m and the reference.

    ``L`` holds one (target, horizon, window) slice with columns ticker, origin, model, col.
    Only (asset, origin) pairs where both models have a finite loss are used.
    Returns a frame indexed by origin with columns ``m``, ``ref``, ``n_assets``.
    """
    a = L.loc[L["model"] == m].set_index(["ticker", "origin"])[col]
    b = L.loc[L["model"] == ref].set_index(["ticker", "origin"])[col]
    j = pd.concat([a, b], axis=1, keys=["m", "ref"]).dropna()
    if j.empty:
        return pd.DataFrame(columns=["m", "ref", "n_assets"])
    g = j.groupby(level="origin")
    out = g.mean()
    out["n_assets"] = g.size()
    return out.sort_index()


def pooled_matrix(L: pd.DataFrame, models: list[str], col: str) -> pd.DataFrame:
    """(origins x models) matrix of cross-sectional mean losses on common (asset, origin) pairs.

    Used for the pooled MCS: only (asset, origin) cells where *every* model has a loss.
    """
    wide = L.loc[L["model"].isin(models)].pivot_table(index=["ticker", "origin"], columns="model", values=col, aggfunc="first")
    wide = wide.reindex(columns=models).dropna()
    if wide.empty:
        return wide
    return wide.groupby(level="origin").mean().sort_index()


def ratio_ci(m: np.ndarray, r: np.ndarray, B: int, block: float, rng: np.random.Generator, level: float = 0.95):
    """Relative loss mean(m)/mean(r) with a stationary-bootstrap percentile CI."""
    from tsfm_rc.eval.bootstrap import stationary_bootstrap_indices

    m = np.asarray(m, float)
    r = np.asarray(r, float)
    point = float(m.mean() / r.mean()) if r.mean() > 0 else np.nan
    if len(m) < 5 or not np.isfinite(point):
        return point, np.nan, np.nan
    idx = stationary_bootstrap_indices(len(m), B, block, rng)
    ratios = m[idx].mean(1) / r[idx].mean(1)
    lo, hi = np.quantile(ratios, [(1 - level) / 2, 1 - (1 - level) / 2])
    return point, float(lo), float(hi)
