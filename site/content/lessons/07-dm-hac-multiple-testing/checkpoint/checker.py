"""Auto-checker for lesson 07: your Holm adjustment vs the study's."""

import numpy as np

from tsfm_rc.eval.multiple import holm


def check(fn) -> None:
    rng = np.random.default_rng(9)
    cases = [np.array([0.01, 0.04, 0.03, 0.005]), rng.uniform(0, 0.2, 27), rng.uniform(0, 1, 10)]
    for p in cases:
        got = np.asarray(fn(p), dtype=float)
        ref = holm(p)[0]
        assert got.shape == ref.shape, f"❌ Return one adjusted p-value per input: expected {ref.shape}, got {got.shape}."
        if not np.allclose(got, ref):
            if np.allclose(got, np.minimum(1, p * len(p))):
                raise AssertionError("❌ That is Bonferroni (every p times m). Holm multiplies the k-th smallest by (m − k + 1).")
            if np.any(got > 1):
                raise AssertionError("❌ Cap adjusted p-values at 1.")
            raise AssertionError("❌ Check the running maximum: adjusted values must not decrease along the sorted order.")
    print("✅ Correct! Your Holm adjustment matches the one used for the primary family.")
