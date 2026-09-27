"""Auto-checker for lesson 03. Compares your function with the repo's ForecastOrigin."""

import numpy as np
import pandas as pd

from tsfm_rc.origin import ForecastOrigin


def check(fn) -> None:
    idx = pd.bdate_range("2021-01-01", periods=300)
    cases = [(300, 200, 1), (300, 200, 5), (300, 250, 20), (300, 3, 5), (300, 299, 1)]
    for n, pos, h in cases:
        expected = ForecastOrigin(idx[pos]).label_available_mask(idx[:n], h)
        got = np.asarray(fn(n, pos, h))
        assert got.shape == (n,), f"❌ Expected an array of length {n}, got shape {got.shape}."
        assert got.dtype == bool, "❌ Return booleans (hint: a comparison like `a <= b`)."
        if not np.array_equal(got, expected):
            wrong = int(np.flatnonzero(got != expected)[0])
            raise AssertionError(
                f"❌ Case n={n}, origin_pos={pos}, h={h}: row {wrong} should be "
                f"{bool(expected[wrong])}. Hint: row i's label covers rows i+1 … i+h."
            )
    print("✅ Correct! Your mask matches ForecastOrigin.label_available_mask on all cases.")
