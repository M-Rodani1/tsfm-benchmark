"""Auto-checker for lesson 01: compares with the study's own target code."""

import numpy as np

from tsfm_rc.data.provider import FixtureProvider
from tsfm_rc.data.targets import daily_series, make_target
from tsfm_rc.paths import FIXTURE_DIR


def check(fn) -> None:
    raw = FixtureProvider(FIXTURE_DIR / "synthetic_ohlcv.csv").fetch("SYN_HAR_A", "2010-01-01", "2026-12-31")
    prices = raw["adj_close"].to_numpy()
    daily = daily_series(raw)
    for h in (1, 5, 20):
        target = make_target(daily, "returns", h).to_numpy()
        for i in (1, 50, 777, 3000):
            got = fn(prices, i, h)
            assert got is not None, "❌ Your function returned None. Did you forget `return`?"
            if not np.isclose(got, target[i], atol=1e-9):
                ratio = got / target[i] if target[i] else float("nan")
                hint = " Looks like you forgot the factor 100." if np.isclose(ratio, 0.01) else ""
                hint = hint or (" Check the direction: price at i+h over price at i." if np.isclose(ratio, -1) else "")
                raise AssertionError(f"❌ i={i}, h={h}: got {got:.6f}, expected {target[i]:.6f}.{hint}")
    print("✅ Correct! Your h-step log return equals the study's target (sum of daily log returns).")
