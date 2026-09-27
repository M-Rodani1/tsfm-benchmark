# %% [markdown]
# # Lesson 10: Writing it up as a short paper
# ⏱ **90 min** · files: `lessons/10-writing-up/paper_template.md`, `reports/RESULTS.md`,
# `docs/PREREGISTRATION.md`
#
# **You'll be able to…**
# 1. lay out a 4–6 page empirical paper and know what goes where;
# 2. write every result sentence with effect size, CI, *corrected* p-value and verdict;
# 3. generate those sentences from stored tables instead of typing numbers;
# 4. match each claim to the evidence that supports it (or not).
#
# **You need:** Lesson 09.

# %%
import pandas as pd

from tsfm_rc.paths import LESSONS_DIR, RESULTS_DIR
from tsfm_rc.reports.results_md import ci, fp

stats = RESULTS_DIR / "smoke" / "stats"
dm_all = pd.read_parquet(stats / "dm_all.parquet")
dm_primary = pd.read_parquet(stats / "dm_primary.parquet")
print((LESSONS_DIR / "10-writing-up" / "paper_template.md").read_text()[:1200])

# %% [markdown]
# ## 1. The shape of the paper
# Read the template above. Two rules make it honest:
# - **Methods before results, written as pre-registered.** Amendments are reported, with dates.
# - **Results in the order of the pre-registration.** Primary family first, whatever it says.
#
# ## 2. One sentence per result, generated
# A result sentence needs: comparison, effect size with CI, corrected p-value, verdict.
#
# 🤔 **Predict before you run:** for `garch` vs `har` (rv, h=5, full period), will the verdict
# be "better" or "no detectable difference"?

# %%
def sentence(r) -> str:
    verdict = ("model better" if r.mean_diff < 0 else "model worse") if r.reject_holm else "no detectable difference"
    return (f"{r.model} vs {r.reference} ({r.target}, h={r.horizon}): relative loss "
            f"{ci(r.rel_loss, r.rel_loss_lo, r.rel_loss_hi)}, Holm p = {fp(r.p_holm)}: {verdict}.")

row = dm_all.query("period == 'full' and window == 'expanding' and model == 'garch' and target == 'rv' and horizon == 5").iloc[0]
print(sentence(row))

# %% [markdown]
# Because the text is produced from the table, a re-run can never leave a stale number in
# your paper.
#
# ## 3. Absent results get a sentence too
# 🤔 **Predict:** what should the paper say about the TSFMs in *this* (synthetic, offline) run?

# %%
n_unavail = (dm_primary["status"] == "UNAVAILABLE").sum()
print(f"{n_unavail} of {len(dm_primary)} primary tests could not be run (model weights unavailable).")

# %% [markdown]
# Write exactly that. "TSFMs did not beat the baselines" would be a false claim.
#
# ## 4. Claims vs evidence
# For each draft claim, find the row that supports it. If there is none, delete the claim.

# %%
claims = {
    "GARCH beats HAR for 5-day volatility (full period)": ("rv", 5, "garch"),
    "Seasonal naive is worse than HAR for volume at h=20": ("volume", 20, "seasonal_naive"),
}
fam = dm_all.query("period == 'full' and window == 'expanding'")
for claim, (target, horizon, model) in claims.items():
    r = fam[(fam.target == target) & (fam.horizon == horizon) & (fam.model == model)].iloc[0]
    print(f"{'SUPPORTED  ' if r.reject_holm else 'UNSUPPORTED'} | {claim} | Holm p = {fp(r.p_holm)}")

# %% [markdown]
# ## 5. Before you submit (checklist)
# - Data section says real or synthetic, the period, the universe *and* survivorship bias.
# - Every model that could not run is named, with the reason.
# - Every p-value in the abstract is a corrected one.
# - Limitations include contamination uncertainty (`docs/PRETRAINING-DATA.md` tags).
# - Related work you cite, you have read. The two TSFM-in-finance papers listed at the end
#   of `docs/PRETRAINING-DATA.md` were found by search and **not** read yet.
#
# ## ✅ Checkpoint
# Write `my_sentence(r)` that returns exactly the same text as `sentence(r)` above, for any
# row of `dm_all` (use `ci` and `fp`).

# %% tags=["exercise"]
def my_sentence(r):
    # YOUR CODE HERE
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(my_sentence)

# %% [markdown] tags=["after-flashcards"]
# **Next:** you have finished the track. Run the real study (`make reproduce`, see README),
# re-read `reports/RESULTS.md`, and draft your paper from `paper_template.md`. Tick lesson 10
# in `lessons/PROGRESS.md`.
