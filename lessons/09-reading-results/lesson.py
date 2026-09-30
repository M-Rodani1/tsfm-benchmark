# GENERATED from site/content/lessons/09-reading-results by `make lessons`: edit the source, not this file.

# %% [markdown]
# # Lesson 09: Reading, and critiquing, our own results
# ⏱ **60 min** · code you will read: `reports/RESULTS.md`, `results/smoke/stats/*.parquet`, `the Results page of this site`
#
# **You'll be able to…**
# 1. trace any number in the report back to the stored table it came from;
# 2. tell a *surviving* finding from one that only looked significant before correction;
# 3. tell an *absent* result from a *null* result;
# 4. run a critique checklist on any forecasting study, starting with this one.
#
# **You need:** Lessons 06–08.

# %% [markdown]
# ## The report and its tables
#
# The report is *rendered* from stored tables, never typed. We load three of them for the
# `smoke` run and print the top of its report.

# %%
import pandas as pd

from tsfm_rc.learn import report_text, stats_table

dm_all = stats_table("smoke", "dm_all")
dm_primary = stats_table("smoke", "dm_primary")
mcs = stats_table("smoke", "mcs")
print(report_text("smoke")[:900])

# %% [markdown]
# The banner matters most: these are **synthetic** fixtures. Nothing here is about markets.

# %% [markdown]
# ## Trace a number
#
# The report lists `garch` vs `har` for rv. Find the same row in the stored table.
#
# 🤔 **Predict before you run:** If you edit a number in RESULTS.md by hand and re-render, what happens?
#
# - Your edit stays
# - It is overwritten by the stored table's value
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **It is overwritten by the stored table's value.** The report is a pure function of the stored tables; a test even checks that re-rendering gives an identical file.
#
# </details>

# %%
row = dm_all.query("period == 'full' and window == 'expanding' and target == 'rv' and model == 'garch' and horizon == 5")
print(row[["rel_loss", "rel_loss_lo", "rel_loss_hi", "dm_stat", "p_value", "p_holm", "T"]].round(3).to_string(index=False))

# %% [markdown]
# ## Raw vs corrected
#
# 🤔 **Predict before you run:** Of the tests with a raw p < 0.05, will all of them survive the Holm correction?
#
# - Yes
# - No, some drop out
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **No, some drop out.** Holm raises the bar for all but the very smallest p-values; borderline ones drop out.
#
# </details>

# %%
fam = dm_all.query("period == 'full' and window == 'expanding'")
raw = fam["p_value"] < 0.05
print(f"{raw.sum()} raw-significant, {fam['reject_holm'].sum()} survive Holm")
print(fam.loc[raw & ~fam["reject_holm"], ["target", "horizon", "model", "p_value", "p_holm"]].round(3).to_string(index=False))

# %% [markdown]
# Those rows are what a less careful study would have published.

# %% [markdown]
# ## Absent is not null
#
# 🤔 **Predict before you run:** What does the primary table say about the foundation models in this run?
#
# - They did not beat the baselines
# - They could not be evaluated (UNAVAILABLE)
# - They beat the baselines
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **They could not be evaluated (UNAVAILABLE).** No weights could be loaded, so there is no evidence either way. Writing 'TSFMs did not beat the baselines' would be false.
#
# </details>

# %%
print(dm_primary["status"].value_counts())

# %% [markdown]
# ## The MCS view
#
# Instead of "who beat the reference?", the Model Confidence Set asks "who cannot be ruled out
# as best?".

# %%
print(mcs.query("period == 'full' and ticker == 'POOLED' and target == 'rv'")
      [["horizon", "model", "mean_loss", "mcs_pvalue", "in_mcs"]].round(3).to_string(index=False))

# %% [markdown]
# ## A critique checklist
#
# Ask these of *any* forecasting result, including ours: real or synthetic data, and which
# period? Could any input come from after the origin? How many origins (T), any `small_sample`
# flags? How many tests, and was the claim corrected? Is the CI narrow enough to matter? Could
# the model have seen the test period? Does it hold with a rolling window?
#
# 🤔 **Predict before you run:** A paper reports one model beating 10 others at p = 0.03 and does not mention the other 9 comparisons. Which checklist item fails first?
#
# - Leakage
# - Multiplicity
# - Contamination
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **Multiplicity.** Ten comparisons were run, but the claim was not corrected for them.
#
# </details>
#
# The Results page of this site shows the same tables interactively.

# %% [markdown]
# ## Checkpoint
#
# Write `verdict(mean_diff, p_holm, alpha=0.05)` returning exactly the report's wording:
# `"model better"`, `"model worse"`, or `"no detectable difference"`.

# %% tags=["exercise"]
def verdict(mean_diff, p_holm, alpha=0.05):
    # YOUR CODE HERE
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(verdict)

# %% [markdown] tags=["flashcards"]
# ## Flashcards
#
# Cover the answer, say it out loud, then check. `make flashcards` exports these to Anki; the website schedules them for review.
#
# 1. **Q:** Where does every number in reports/RESULTS.md come from?
#    - **A:** From stored tables in results/<run>/stats/*.parquet, listed with their SHA-256 in the Provenance section.
# 2. **Q:** What is the difference between an absent result and a null result?
#    - **A:** Absent = the model could not be evaluated (UNAVAILABLE), so no evidence either way; null = evaluated, no detectable difference.
# 3. **Q:** A comparison has raw p = 0.01 but Holm p = 0.20. Is it a finding?
#    - **A:** No. It does not survive the pre-specified multiple-testing correction.
# 4. **Q:** What does a relative loss of 0.95 [0.90, 1.01] mean?
#    - **A:** The model's loss is 5% below the reference on average, but the 95% CI includes 1 (no difference).
# 5. **Q:** What does it mean if the MCS contains several models?
#    - **A:** The data cannot distinguish them from the best model at the chosen confidence level.
# 6. **Q:** Why flag tests with fewer than 100 origins?
#    - **A:** The DM test's actual size is above nominal in small samples, so marginal p-values are unreliable.
# 7. **Q:** Name four items of the critique checklist.
#    - **A:** Real vs synthetic data, leakage, sample size, multiplicity (also effect size, contamination, robustness).

# %% [markdown] tags=["after-flashcards"]
# **Next:** open `lessons/10-writing-up/lesson.ipynb` (Writing it up as a short paper). Tick lesson 09 in `lessons/PROGRESS.md`.
