# GENERATED from site/content/lessons/08-contamination by `make lessons`: edit the source, not this file.

# %% [markdown]
# # Lesson 08: Contamination, and how our test works
# ⏱ **60 min** · code you will read: `src/tsfm_rc/contamination/windows.py`, `src/tsfm_rc/eval/contamination_test.py`, `docs/PRETRAINING-DATA.md`
#
# **You'll be able to…**
# 1. explain why a model that saw the test period during pretraining can look too good;
# 2. build "possibly seen" and "clean" windows from release dates;
# 3. compute the contamination statistic Δ and read its CI;
# 4. say what the placebo and the synthetic control add, and what they cannot fix.
#
# **You need:** Lessons 05 and 07.

# %% [markdown]
# ## The worry
#
# TSFMs were trained on huge public collections. If SPY's 2019 prices were in there, a
# "forecast" of 2019 could be partly *recall*. Data **after** a model's public release cannot
# have been in its training set, so that period is **clean**.

# %%
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tsfm_rc.config import load_config
from tsfm_rc.contamination.windows import common_clean_start, windows_for_models
from tsfm_rc.eval.contamination_test import contamination_delta

cfg = load_config("configs/default.yaml")
windows = windows_for_models(cfg)
fig, ax = plt.subplots(figsize=(9, 2.2))
for i, w in enumerate(windows.values()):
    ax.barh(i, (w.effective_release - w.test_start).days, left=w.test_start, color="tab:red", alpha=0.5)
    ax.barh(i, (pd.Timestamp(cfg.data.end) - w.clean_start).days, left=w.clean_start, color="tab:green")
ax.set_yticks(range(len(windows)), list(windows)); ax.set_title("red: possibly seen · green: clean");
print("common clean window starts", common_clean_start(windows).date())

# %% [markdown]
# ## Labelling a forecast
#
# A forecast is "seen" only if its **whole** target window ended before the release; "clean"
# if it was made ≥ 30 days after the release; otherwise it falls in the gap and is not used.
#
# 🤔 **Predict before you run:** A 20-day target made on 2024-11-15 for Chronos-Bolt (released 2024-11-26): seen, clean, or gap?
#
# - seen
# - clean
# - gap
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **gap.** Its target window ends after the release, so it is not 'seen'; it was made before release + 30 days, so it is not 'clean'.
#
# </details>

# %%
cb = windows["chronos_bolt_tiny"]
origins = pd.Series(pd.to_datetime(["2019-03-01", "2024-11-15", "2025-02-03"]))
ends = pd.Series(pd.to_datetime(["2019-03-29", "2024-12-13", "2025-03-03"]))
print(cb.label(origins, ends).tolist())

# %% [markdown]
# ## The statistic
#
# `R_w` = (total TSFM loss) / (total reference loss) in window w, and `Δ = ln R_clean − ln R_seen`.
# Memorisation means relatively better where it saw the data, so **Δ > 0**. Ratios, not
# differences: if the clean period is simply more volatile, *both* losses grow and the ratio
# does not move.
#
# 🤔 **Predict before you run:** Fake losses where the clean period is 3× noisier, and the TSFM is 5% better than the reference everywhere: what Δ do you expect?
#
# - Clearly positive
# - About zero
# - Clearly negative
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **About zero.** The relative performance is the same in both windows, so the ratios match and Δ ≈ 0, however noisy the clean period is.
#
# </details>

# %%
rng = np.random.default_rng(0)
ref_seen, ref_clean = rng.gamma(2, 1, 300), 3 * rng.gamma(2, 1, 150)
def noise(n):
    return rng.gamma(10, 0.1, n)                 # day-to-day scatter around the ratio

honest = contamination_delta(0.95 * ref_seen * noise(300), ref_seen, 0.95 * ref_clean * noise(150), ref_clean, B=500, h_eff=1, rng=rng)
cheat = contamination_delta(0.70 * ref_seen * noise(300), ref_seen, 0.95 * ref_clean * noise(150), ref_clean, B=500, h_eff=1, rng=rng)
for name, r in [("honest", honest), ("memoriser", cheat)]:
    print(f"{name:9s} Δ = {r['delta']:+.3f}  95% CI [{r['ci_lo']:+.3f}, {r['ci_hi']:+.3f}]  p = {r['p_one_sided']:.3f}")

# %% [markdown]
# ## Placebo, synthetic control, and limits
#
# Regimes differ in more than scale (COVID sits in the seen window). A **placebo** computes the
# same Δ for two *baselines*; neither can memorise, so their Δ shows how much regime alone
# moves the statistic. We say "evidence consistent with memorisation" only if the TSFM's Δ is
# Holm-significant **and** above the placebo's CI. The **synthetic control** feeds every model
# simulated series nobody has seen.
#
# 🤔 **Predict before you run:** The TSFM's Δ is significant but sits inside the placebo's CI. What do we report?
#
# - Evidence of memorisation
# - Not distinguishable from a regime effect
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **Not distinguishable from a regime effect.** The placebo moved just as much without any possibility of memorisation, so the TSFM's Δ could be regime alone.
#
# </details>
#
# **Limits:** clean windows are short (≈ 1 year for TimesFM 2.5; amendment A4 uses every trading
# day in them); a null result means "no evidence", not "no contamination"; training corpora are
# only partly documented (tags in `docs/PRETRAINING-DATA.md`).

# %% [markdown]
# ## Checkpoint
#
# Write `my_delta(m_seen, ref_seen, m_clean, ref_clean)` returning Δ from NumPy arrays of
# losses.

# %% tags=["exercise"]
def my_delta(m_seen, ref_seen, m_clean, ref_clean):
    # YOUR CODE HERE
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(my_delta)

# %% [markdown] tags=["flashcards"]
# ## Flashcards
#
# Cover the answer, say it out loud, then check. `make flashcards` exports these to Anki; the website schedules them for review.
#
# 1. **Q:** What is pretraining-data contamination?
#    - **A:** The evaluation period's data were (possibly) in the model's training set, so good scores may reflect recall, not forecasting.
# 2. **Q:** Which data can definitely not be in a model's pretraining set?
#    - **A:** Data after the model's public release (after the weights were fixed).
# 3. **Q:** When is a forecast labelled "possibly seen"?
#    - **A:** When its whole target window ended before the model's (effective) release date.
# 4. **Q:** When is a forecast labelled "clean"?
#    - **A:** When its origin is at least 30 days after the effective release date.
# 5. **Q:** Define the contamination statistic Delta.
#    - **A:** Delta = ln R_clean − ln R_seen, with R = total TSFM loss / total reference loss in that window.
# 6. **Q:** Why use a ratio of losses rather than a difference?
#    - **A:** A regime that scales both models' losses equally (e.g. a more volatile period) leaves the ratio unchanged.
# 7. **Q:** What does the placebo test show?
#    - **A:** How much Delta moves between the windows for models that cannot memorise (baseline pairs), i.e. regime effects.
# 8. **Q:** What does a non-significant Delta mean?
#    - **A:** No evidence of memorisation with this power; it is not proof that the model never saw the data.

# %% [markdown] tags=["after-flashcards"]
# **Next:** open `lessons/09-reading-results/lesson.ipynb` (Reading, and critiquing, our own results). Tick lesson 08 in `lessons/PROGRESS.md`.
