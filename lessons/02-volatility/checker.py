"""Auto-checker for lesson 02: compares with the repo's garman_klass_variance."""

import numpy as np
import pandas as pd

from tsfm_rc.data.targets import garman_klass_variance


def check(fn) -> None:
    rng = np.random.default_rng(7)
    n = 500
    lo = 100 * np.exp(rng.uniform(-0.05, 0, n))
    hi = lo * np.exp(rng.uniform(0.001, 0.05, n))
    o = lo + (hi - lo) * rng.uniform(size=n)
    c = lo + (hi - lo) * rng.uniform(size=n)
    got = np.asarray(fn(o, hi, lo, c), dtype=float)
    ref = garman_klass_variance(pd.Series(o), pd.Series(hi), pd.Series(lo), pd.Series(c)).to_numpy()
    assert got.shape == ref.shape, f"❌ Expected {ref.shape[0]} values, got shape {got.shape}."
    if not np.allclose(got, ref, rtol=1e-10):
        r = np.nanmedian(got / ref)
        hint = ""
        if np.isclose(r, 1e-4, rtol=1e-3):
            hint = " Multiply by 100² = 1e4 to get %²."
        elif np.all(got >= ref):
            hint = " Check the sign and constant of the open-close term: −(2 ln 2 − 1)."
        raise AssertionError(f"❌ Values differ (median ratio {r:.4g}).{hint}")
    print("✅ Correct! Your GK matches the study's estimator on 500 random valid days.")
