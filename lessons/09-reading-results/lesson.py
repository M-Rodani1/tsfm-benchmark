# %% [markdown]
# # Lesson 09: Reading, and critiquing, our own results
# ⏱ **60 min** · files you will read: `reports/RESULTS.md`, `results/smoke/stats/*.parquet`,
# `reports/dashboard/index.html`
#
# **You'll be able to…**
# 1. trace any number in the report back to the stored table it came from;
# 2. tell a *surviving* finding from one that only looked significant before correction;
# 3. tell an *absent* result from a *null* result;
# 4. run a critique checklist on any forecasting study, starting with this one.
#
# **You need:** Lessons 06–08.

# %%
import pandas as pd

from tsfm_rc.paths import REPORTS_DIR, RESULTS_DIR

stats = RESULTS_DIR / "smoke" / "stats"
dm_all = pd.read_parquet(stats / "dm_all.parquet")
dm_primary = pd.read_parquet(stats / "dm_primary.parquet")
mcs = pd.read_parquet(stats / "mcs.parquet")
print((REPORTS_DIR / "smoke" / "RESULTS.md").read_text()[:900])

# %% [markdown]
# The banner matters most: these are **synthetic** fixtures. Nothing below is about markets.
#
# ## 1. Trace a number
# Section 4 of the report lists `garch` vs `har` for rv. Find the same row in the table.

# %%
row = dm_all.query("period == 'full' and window == 'expanding' and target == 'rv' and model == 'garch' and horizon == 5")
print(row[["rel_loss", "rel_loss_lo", "rel_loss_hi", "dm_stat", "p_value", "p_holm", "T"]].round(3).to_string(index=False))

# %% [markdown]
# Same numbers as the report, because the report is *rendered* from this file (a test checks
# that re-rendering gives an identical file).
#
# ## 2. Raw vs corrected
# 🤔 **Predict before you run:** of the tests with raw p < 0.05, what fraction survive Holm?

# %%
fam = dm_all.query("period == 'full' and window == 'expanding'")
raw = fam["p_value"] < 0.05
print(f"{raw.sum()} raw-significant, {fam['reject_holm'].sum()} survive Holm")
print(fam.loc[raw & ~fam["reject_holm"], ["target", "horizon", "model", "p_value", "p_holm"]].round(3).to_string(index=False))

# %% [markdown]
# Those rows are what a less careful study would have published.
#
# ## 3. Absent is not null
# 🤔 **Predict:** what does the primary table say about the TSFMs in this run?

# %%
print(dm_primary["status"].value_counts())

# %% [markdown]
# "UNAVAILABLE" means *no evidence either way*. Writing "TSFMs did not beat the baselines"
# here would be a false statement.
#
# ## 4. The MCS view
# Instead of "who beat the reference?", the MCS asks "who cannot be ruled out as best?".

# %%
print(mcs.query("period == 'full' and ticker == 'POOLED' and target == 'rv'")
      [["horizon", "model", "mean_loss", "mcs_pvalue", "in_mcs"]].round(3).to_string(index=False))

# %% [markdown]
# ## 5. A critique checklist
# Ask these of *any* forecasting result, including ours:
# 1. **Data:** real or synthetic? Which period? Survivorship?
# 2. **Leakage:** could any input have come from after the origin?
# 3. **Sample size:** how many origins (T)? Any `small_sample` flags?
# 4. **Multiplicity:** how many tests were run, and was the claim corrected?
# 5. **Effect size:** is the CI narrow enough to matter, or just "significant"?
# 6. **Contamination:** could the model have seen the test period?
# 7. **Robustness:** does it hold with a rolling window? In the synthetic control?
#
# Open `reports/dashboard/index.html` in a browser to explore the same tables interactively.
#
# ## ✅ Checkpoint
# Write `verdict(mean_diff, p_holm, alpha=0.05)` that returns exactly the report's wording:
# `"model better"`, `"model worse"`, or `"no detectable difference"`.

# %% tags=["exercise"]
def verdict(mean_diff, p_holm, alpha=0.05):
    # YOUR CODE HERE
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(verdict)

# %% [markdown] tags=["after-flashcards"]
# **Next:** open `lessons/10-writing-up/lesson.ipynb` (turning this into a short paper).
# Tick lesson 09 in `lessons/PROGRESS.md`.
