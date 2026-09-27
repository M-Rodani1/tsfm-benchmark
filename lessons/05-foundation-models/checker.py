"""Auto-checker for lesson 05: your lognormal mean vs the study's conversion rule."""

import numpy as np

from tsfm_rc.models.tsfm import Z90, to_target_scale


def check(fn) -> None:
    rng = np.random.default_rng(11)
    z = np.array([-Z90, -0.8416, -0.5244, -0.2533, 0, 0.2533, 0.5244, 0.8416, Z90])
    for _ in range(20):
        m, s = rng.normal(0, 1), rng.uniform(0.1, 1.2)
        dec = np.tile(m + s * z, (1, 1))
        ref = to_target_scale("rv", dec[:, 4], dec, [1])[0][1]
        got = fn(m, m - s * Z90, m + s * Z90)
        if got is None:
            raise AssertionError("❌ Your function returned None. Did you forget `return`?")
        if not np.isclose(got, ref, rtol=1e-3):
            if np.isclose(got, np.exp(m), rtol=1e-3):
                raise AssertionError("❌ That is exp(median): the MEDIAN of exp(X). Add s²/2 inside exp.")
            if np.isclose(got, np.exp(m + s), rtol=1e-3):
                raise AssertionError("❌ Use s²/2, not s.")
            raise AssertionError(f"❌ For median={m:.3f}, s={s:.3f}: expected {ref:.4f}, got {got:.4f}.")
    print("✅ Correct! This is exactly how the study converts log-variance quantiles to a variance forecast.")
