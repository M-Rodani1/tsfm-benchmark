"""Auto-checker for lesson 04: your GARCH recursion vs a reference and the fixture truth."""

import json

import numpy as np
import pandas as pd

from tsfm_rc.data.provider import FixtureProvider
from tsfm_rc.data.targets import daily_series
from tsfm_rc.paths import FIXTURE_DIR


def _ref(eps, omega, alpha, beta, s0):
    s = [s0]
    for e in eps[:-1]:
        s.append(omega + alpha * e**2 + beta * s[-1])
    return np.array(s)


def check(fn) -> None:
    rng = np.random.default_rng(3)
    eps = rng.standard_normal(50)
    got = np.asarray(fn(eps, 0.1, 0.1, 0.8, 1.0), dtype=float)
    ref = _ref(eps, 0.1, 0.1, 0.8, 1.0)
    assert got.shape == ref.shape, f"❌ Return one value per day: expected {ref.shape}, got {got.shape}."
    if got[0] != 1.0:
        raise AssertionError("❌ s[0] must equal s0 (the variance of the first day).")
    if not np.allclose(got, ref):
        if np.allclose(got[1:], [0.1 + 0.1 * e**2 + 0.8 * 1.0 for e in eps[1:]]):
            raise AssertionError("❌ Use the *previous* day's variance s[t-1], not s0 every time.")
        if np.allclose(got[1:-1], ref[2:]):
            raise AssertionError("❌ Off by one: s[t] uses eps[t-1] (yesterday's shock).")
        raise AssertionError("❌ Values differ from s[t] = omega + alpha*eps[t-1]**2 + beta*s[t-1].")
    man = json.loads((FIXTURE_DIR / "MANIFEST.json").read_text())["specs"]["SYN_GARCH_A"]["variance"]
    d = daily_series(FixtureProvider(FIXTURE_DIR / "synthetic_ohlcv.csv").fetch("SYN_GARCH_A", "2010-01-01", "2026-12-31"))
    lat = pd.read_csv(FIXTURE_DIR / "synthetic_latent.csv")
    truth = lat.loc[lat.ticker == "SYN_GARCH_A", "sigma2"].to_numpy()[1:]
    eps = (d["r"] - man["mu"]).to_numpy()[1:]  # day 0 has no previous close
    mine = np.asarray(fn(eps, man["omega"], man["alpha"], man["beta"], truth[0]))
    assert np.allclose(mine, truth, rtol=1e-4), "❌ Works on random data but not on the fixture. NaNs?"
    print("✅ Correct! Your recursion reproduces the true variance of SYN_GARCH_A for all days.")
