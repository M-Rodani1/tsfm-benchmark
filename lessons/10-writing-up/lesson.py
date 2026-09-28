# GENERATED from site/content/lessons/10-writing-up by `make lessons`: edit the source, not this file.

# %% [markdown]
# # Lesson 10: Writing it up as a short paper
# ⏱ **90 min** · code you will read: `paper_template.md (this lesson)`, `reports/RESULTS.md`, `docs/PREREGISTRATION.md`
#
# **You'll be able to…**
# 1. lay out a 4–6 page empirical paper and know what goes where;
# 2. write every result sentence with effect size, CI, *corrected* p-value and verdict;
# 3. generate those sentences from stored tables instead of typing numbers;
# 4. match each claim to the evidence that supports it (or not).
#
# **You need:** Lesson 09.

# %% [markdown]
# ## The shape of the paper
#
# Two rules make it honest. **Methods before results, written as pre-registered**, with every
# amendment reported and dated. **Results in the order of the pre-registration**: primary
# family first, whatever it says.

# %%
import pandas as pd

from tsfm_rc.learn import stats_table
from tsfm_rc.reports.fmt import ci, fp

dm_all = stats_table("smoke", "dm_all")
dm_primary = stats_table("smoke", "dm_primary")
print(open("paper_template.md", encoding="utf-8").read()[:1200])

# %% [markdown]
# ## One sentence per result, generated
#
# A result sentence needs the comparison, the effect size with its CI, the corrected p-value
# and a verdict.
#
# 🤔 **Predict before you run:** For `garch` vs `har` (rv, h = 5, full period) the point estimate says GARCH's loss is clearly lower. Will the verdict be "model better"?
#
# - Yes: its loss is lower
# - No: no detectable difference
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **No: no detectable difference.** Look at the printed sentence: the 95% CI of the relative loss includes 1 and the Holm-adjusted p is far above 0.05. A large-looking effect that the data cannot separate from luck.
#
# </details>

# %%
def sentence(r) -> str:
    verdict = ("model better" if r.mean_diff < 0 else "model worse") if r.reject_holm else "no detectable difference"
    return (f"{r.model} vs {r.reference} ({r.target}, h={r.horizon}): relative loss "
            f"{ci(r.rel_loss, r.rel_loss_lo, r.rel_loss_hi)}, Holm p = {fp(r.p_holm)}: {verdict}.")

row = dm_all.query("period == 'full' and window == 'expanding' and model == 'garch' and target == 'rv' and horizon == 5").iloc[0]
print(sentence(row))

# %% [markdown]
# Because the text is produced from the table, a re-run can never leave a stale number in your
# paper.

# %% [markdown]
# ## Absent results get a sentence too
#
# 🤔 **Predict before you run:** What should the paper say about the TSFMs in *this* (synthetic, offline) run?
#
# - TSFMs did not beat the baselines
# - The TSFMs could not be evaluated, with the reason
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **The TSFMs could not be evaluated, with the reason.** Without model outputs there is no evidence either way; the paper must say the tests could not be run, and why.
#
# </details>

# %%
n_unavail = (dm_primary["status"] == "UNAVAILABLE").sum()
print(f"{n_unavail} of {len(dm_primary)} primary tests could not be run (model weights unavailable).")

# %% [markdown]
# ## Claims vs evidence
#
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
# Before you submit: the data section says real or synthetic, the period, the universe *and* its
# survivorship bias; every model that could not run is named, with the reason; every p-value in
# the abstract is a corrected one; related work you cite, you have read.

# %% [markdown]
# ## Checkpoint
#
# Write `my_sentence(r)` that returns exactly the same text as `sentence(r)` above, for any
# row of `dm_all` (use `ci` and `fp`).

# %% tags=["exercise"]
def my_sentence(r):
    # YOUR CODE HERE
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(my_sentence)

# %% [markdown] tags=["flashcards"]
# ## Flashcards
#
# Cover the answer, say it out loud, then check. `make flashcards` exports these to Anki; the website schedules them for review.
#
# 1. **Q:** What four things does every result sentence need?
#    - **A:** The comparison, the effect size with its CI, the corrected p-value, and the verdict.
# 2. **Q:** Why generate result sentences from stored tables instead of typing them?
#    - **A:** A re-run can then never leave a stale or mistyped number in the paper.
# 3. **Q:** In what order should results be reported?
#    - **A:** The pre-registered order, primary family first, regardless of what it shows.
# 4. **Q:** How do you report a model that could not be evaluated?
#    - **A:** Name it, give the reason, and state that no evidence exists either way (absent, not null).
# 5. **Q:** What must a limitations section of this study mention?
#    - **A:** Survivorship bias, the volatility proxy, contamination uncertainty, regime confounding, small clean windows, amendments.
# 6. **Q:** Can you cite a paper you found by search but have not read?
#    - **A:** No. Read it first, or leave it out.

# %% [markdown] tags=["after-flashcards"]
# **Next:** you have finished the track. Run the real study (`make reproduce`, see README), re-read `reports/RESULTS.md`, and draft your paper from `paper_template.md`. Tick lesson 10 in `lessons/PROGRESS.md`.
