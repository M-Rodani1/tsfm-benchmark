"""Auto-checker for lesson 09: your verdicts vs the stored Holm decisions."""

from tsfm_rc.learn import stats_table


def check(fn) -> None:
    dm = stats_table("smoke", "dm_all")
    for r in dm.itertuples(index=False):
        expected = ("model better" if r.mean_diff < 0 else "model worse") if r.reject_holm else "no detectable difference"
        got = fn(r.mean_diff, r.p_holm)
        if got != expected:
            hint = ""
            if r.p_value < 0.05 <= r.p_holm:
                hint = " This row is significant only BEFORE correction: use the Holm p-value."
            elif got in ("model better", "model worse") and expected != got:
                hint = " Check the sign: negative mean_diff = model has LOWER loss = better."
            raise AssertionError(f"❌ {r.model} {r.target} h={r.horizon}: expected '{expected}', got '{got}'.{hint}")
    print(f"✅ Correct on all {len(dm)} comparisons in the stored smoke results (dm_all).")
