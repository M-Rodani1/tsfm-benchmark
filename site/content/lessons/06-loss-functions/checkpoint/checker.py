"""Auto-checker for lesson 06: your QLIKE vs the study's."""

import numpy as np

from tsfm_rc.eval.metrics import qlike


def check(fn) -> None:
    rng = np.random.default_rng(5)
    y = rng.gamma(2, 1, 200)
    f = rng.gamma(2, 1, 200)
    got = np.asarray(fn(y, f), dtype=float)
    ref = qlike(y, f)
    assert got.shape == ref.shape, f"❌ Return one loss per observation: expected {ref.shape}, got {got.shape}."
    if not np.allclose(got, ref):
        alt = np.log(f) + y / f  # the un-normalised textbook form
        if np.allclose(got, alt):
            raise AssertionError("❌ That is the un-normalised form ln f + y/f. Use y/f − ln(y/f) − 1 (it is 0 at f = y).")
        if np.allclose(got, f / y - np.log(f / y) - 1):
            raise AssertionError("❌ Ratio upside down: it is y/f (truth over forecast).")
        raise AssertionError("❌ Values differ from y/f − ln(y/f) − 1.")
    assert np.allclose(fn(np.array([2.0]), np.array([2.0])), 0.0), "❌ A perfect forecast should have loss 0."
    print("✅ Correct! This is the QLIKE used as the primary volatility loss.")
