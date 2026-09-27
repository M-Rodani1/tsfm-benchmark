"""Model Confidence Set (Hansen, Lunde & Nason 2011, Econometrica 79(2)).

Given a (T x m) loss matrix, the MCS at level alpha is the set of models that cannot be
rejected as "not the best" with confidence 1 - alpha. Sequential elimination:

  while more than one model remains:
      test H0: all remaining models have equal expected loss
      if rejected, eliminate the worst model; its MCS p-value is the running max of p-values
  the last model gets p-value 1; the MCS = {models with MCS p-value >= alpha}

Statistics (both with the same bootstrap indices for every step):
- ``Tmax``: t_i = (Lbar_i - mean_j Lbar_j) / se_i, T = max_i t_i, eliminate argmax (pre-registered)
- ``TR``:   t_ij = (Lbar_i - Lbar_j) / se_ij, T = max_ij |t_ij|, eliminate argmax_i max_j t_ij

Standard errors come from the stationary bootstrap. The implementation follows the same
recentring as ``arch.bootstrap.MCS`` and is tested to reproduce it exactly given the same
bootstrap indices.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from tsfm_rc.eval.bootstrap import stationary_bootstrap_indices


@dataclass
class MCSResult:
    pvalues: pd.Series  # MCS p-value per model
    alpha: float
    statistic: str

    @property
    def included(self) -> list[str]:
        return [m for m, p in self.pvalues.items() if p >= self.alpha]

    def table(self) -> pd.DataFrame:
        df = self.pvalues.rename("mcs_pvalue").to_frame()
        df["in_mcs"] = df["mcs_pvalue"] >= self.alpha
        df.index.name = "model"
        return df.reset_index()


def model_confidence_set(
    losses: np.ndarray | pd.DataFrame,
    alpha: float = 0.10,
    *,
    B: int = 1000,
    block: float = 5.0,
    statistic: str = "Tmax",
    rng: np.random.Generator | None = None,
    indices: np.ndarray | None = None,
    names: Sequence[str] | None = None,
) -> MCSResult:
    if isinstance(losses, pd.DataFrame):
        names = list(losses.columns) if names is None else names
        L = losses.to_numpy(dtype=float)
    else:
        L = np.asarray(losses, float)
        names = list(names) if names is not None else [f"m{i}" for i in range(L.shape[1])]
    T, k = L.shape
    if k < 2:
        raise ValueError("need at least two models")
    if not np.isfinite(L).all():
        raise ValueError("losses contain NaN/inf; align models on common dates first")
    if indices is None:
        indices = stationary_bootstrap_indices(T, B, block, rng or np.random.default_rng(0))
    eliminated: list[tuple[int, float]] = []
    if statistic == "Tmax":
        err = L - L.mean(0)
        bs = np.stack([err[ix].mean(0) for ix in indices])  # (B, k) bootstrap mean deviations
        bs -= bs.mean(1, keepdims=True)
        included = np.ones(k, dtype=bool)
        while included.sum() > 1:
            cols = np.flatnonzero(included)
            b = bs[:, cols] - bs[:, cols].mean(1, keepdims=True)
            sd = np.sqrt((b**2).mean(0))
            sd = np.where(sd > 0, sd, np.nan)
            lbar = L[:, cols].mean(0)
            t = (lbar - lbar.mean()) / sd
            stat = np.nanmax(t)
            sim = np.nanmax(b / sd, axis=1)
            p = float((stat < sim).mean())
            worst = cols[np.flatnonzero(t == stat)]
            for w in np.atleast_1d(worst):
                eliminated.append((int(w), p))
            included[worst] = False
    elif statistic == "TR":
        lbar = L.mean(0)
        diffs = lbar[:, None] - lbar[None, :]
        bsd = np.stack([(L[ix].mean(0)[:, None] - L[ix].mean(0)[None, :]) for ix in indices]) - diffs
        var = (bsd**2).mean(0) + np.eye(k)
        z = diffs / np.sqrt(var)
        zb = bsd / np.sqrt(var)
        included = np.ones(k, dtype=bool)
        while included.sum() > 1:
            cols = np.flatnonzero(included)
            sub = z[np.ix_(cols, cols)]
            stat = sub.max()
            sim = zb[:, cols][:, :, cols].max(axis=(1, 2))
            p = float((stat < sim).mean())
            i = int(np.argwhere(sub == stat)[0][0])
            eliminated.append((int(cols[i]), p))
            included[cols[i]] = False
    else:
        raise ValueError(f"unknown statistic {statistic}")
    for r in np.flatnonzero(included):
        eliminated.append((int(r), 1.0))
    # MCS p-values are the running maximum along the elimination order
    running, out = 0.0, {}
    for i, p in eliminated:
        running = max(running, p)
        out[names[i]] = running
    return MCSResult(pd.Series(out, dtype=float), alpha, statistic)
