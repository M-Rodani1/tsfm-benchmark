"""Auto-checker for lesson 10: result sentences generated from stored tables."""

import pandas as pd

from tsfm_rc.paths import RESULTS_DIR
from tsfm_rc.reports.results_md import ci, fp


def _ref(r) -> str:
    verdict = ("model better" if r.mean_diff < 0 else "model worse") if r.reject_holm else "no detectable difference"
    return (f"{r.model} vs {r.reference} ({r.target}, h={r.horizon}): relative loss "
            f"{ci(r.rel_loss, r.rel_loss_lo, r.rel_loss_hi)}, Holm p = {fp(r.p_holm)}: {verdict}.")


def check(fn) -> None:
    dm = pd.read_parquet(RESULTS_DIR / "smoke" / "stats" / "dm_all.parquet")
    for r in dm.itertuples(index=False):
        got, want = fn(r), _ref(r)
        if got != want:
            hint = " Use the Holm p-value and reject_holm, not the raw p." if "Holm" not in str(got) else ""
            raise AssertionError(f"❌ For {r.model} {r.target} h={r.horizon}:\n  got:  {got}\n  want: {want}{hint}")
    print(f"✅ Correct for all {len(dm)} rows: your paper can now be generated from the stored results.")
