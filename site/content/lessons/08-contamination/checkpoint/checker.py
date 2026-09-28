"""Auto-checker for lesson 08: your Delta vs the study's contamination statistic."""

import numpy as np

from tsfm_rc.eval.contamination_test import contamination_delta


def check(fn) -> None:
    rng = np.random.default_rng(21)
    for _ in range(5):
        rs, rc = rng.gamma(2, 1, 80), rng.gamma(2, 1, 60)
        ms, mc = rs * rng.uniform(0.6, 1.2), rc * rng.uniform(0.6, 1.2)
        ref = contamination_delta(ms, rs, mc, rc, B=10, h_eff=1, rng=rng)["delta"]
        got = fn(ms, rs, mc, rc)
        if got is None:
            raise AssertionError("❌ Your function returned None. Did you forget `return`?")
        if not np.isclose(got, ref):
            if np.isclose(got, -ref):
                raise AssertionError("❌ Sign flipped: Δ = ln R_clean − ln R_seen (clean first).")
            if np.isclose(got, np.log(np.mean(mc / rc)) - np.log(np.mean(ms / rs))):
                raise AssertionError("❌ Use the ratio of SUMS (total losses), not the mean of per-day ratios.")
            raise AssertionError(f"❌ Expected {ref:.4f}, got {got:.4f}.")
    print("✅ Correct! This is the contamination statistic of pre-registration section 9.")
