"""Contamination-difference test (PREREGISTRATION.md section 9).

For a TSFM m and its reference baseline, with pooled normalised losses per origin:

    R_w     = sum_{t in w} Lbar_{m,t} / sum_{t in w} Lbar_{ref,t}     (w = seen, clean)
    Delta   = ln R_clean - ln R_seen

Memorisation predicts the TSFM is relatively better where it may have seen the data, i.e.
R_seen < R_clean and Delta > 0. The two windows are disjoint periods, so each is resampled
independently with the stationary bootstrap (blocks keep serial dependence; resampling
whole origins keeps the cross-section intact). We report the 95% percentile CI and the
one-sided bootstrap p-value P*(Delta* <= 0) for H1: Delta > 0.

The same statistic for a baseline pair that cannot memorise (placebo) shows how much Delta
moves because the two periods differ in market regime.
"""

from __future__ import annotations

import numpy as np

from tsfm_rc.eval.bootstrap import block_length, stationary_bootstrap_indices


def contamination_delta(
    m_seen: np.ndarray,
    ref_seen: np.ndarray,
    m_clean: np.ndarray,
    ref_clean: np.ndarray,
    *,
    B: int,
    h_eff: int,
    rng: np.random.Generator,
) -> dict:
    arrays = [np.asarray(a, float) for a in (m_seen, ref_seen, m_clean, ref_clean)]
    ms, rs, mc, rc = arrays
    out = {"T_seen": len(ms), "T_clean": len(mc)}
    if len(ms) < 5 or len(mc) < 5 or rs.sum() <= 0 or rc.sum() <= 0:
        return {**out, "R_seen": np.nan, "R_clean": np.nan, "delta": np.nan,
                "ci_lo": np.nan, "ci_hi": np.nan, "p_one_sided": np.nan, "flag": "insufficient_data"}
    R_seen = ms.sum() / rs.sum()
    R_clean = mc.sum() / rc.sum()
    delta = float(np.log(R_clean) - np.log(R_seen))
    i_s = stationary_bootstrap_indices(len(ms), B, block_length(len(ms), h_eff), rng)
    i_c = stationary_bootstrap_indices(len(mc), B, block_length(len(mc), h_eff), rng)
    d_star = np.log(mc[i_c].sum(1) / rc[i_c].sum(1)) - np.log(ms[i_s].sum(1) / rs[i_s].sum(1))
    lo, hi = np.quantile(d_star, [0.025, 0.975])
    return {
        **out,
        "R_seen": float(R_seen),
        "R_clean": float(R_clean),
        "delta": delta,
        "ci_lo": float(lo),
        "ci_hi": float(hi),
        "p_one_sided": float(np.mean(d_star <= 0.0)),
        "flag": "",
    }
