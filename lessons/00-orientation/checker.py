"""Auto-checker for lesson 00: count of pre-registered primary tests."""

import pandas as pd

from tsfm_rc.config import load_config
from tsfm_rc.paths import RESULTS_DIR


def check(fn) -> None:
    cfg = load_config("configs/default.yaml")
    got = fn(cfg)
    stored = len(pd.read_parquet(RESULTS_DIR / "smoke" / "stats" / "dm_primary.parquet"))
    if got is None:
        raise AssertionError("❌ Your function returned None. Did you forget `return`?")
    if got != stored:
        raise AssertionError(f"❌ Got {got}. The stored primary table has {stored} rows. "
                             "Hint: multiply the numbers of TSFMs, targets and horizons in the config.")
    full = load_config("configs/full.yaml")
    assert fn(full) == len(full.models.tsfms) * 9, "❌ Read the counts from the config, don't hard-code 27."
    print(f"✅ Correct! {got} primary tests: that is why a multiple-testing correction is needed (lesson 07).")
