# %% [markdown]
# # Lesson 08: Contamination, and how our test works
# ⏱ **60 min** · code you will read: `src/tsfm_rc/contamination/windows.py`,
# `src/tsfm_rc/eval/contamination_test.py`, `docs/PRETRAINING-DATA.md`
#
# **You'll be able to…**
# 1. explain why a model that saw the test period during pretraining can look too good;
# 2. build "possibly seen" and "clean" windows from release dates;
# 3. compute the contamination statistic Δ and read its CI;
# 4. say what the placebo and the synthetic control add, and what they cannot fix.
#
# **You need:** Lessons 05 and 07.

# %%
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tsfm_rc.config import load_config
from tsfm_rc.contamination.windows import common_clean_start, windows_for_models
from tsfm_rc.eval.contamination_test import contamination_delta

cfg = load_config("configs/default.yaml")
windows = windows_for_models(cfg)

# %% [markdown]
# ## 1. The worry
# TSFMs were trained on huge public collections. If SPY's 2019 prices were in there, a
# "forecast" of 2019 could be partly *recall*. Data **after** a model's public release cannot
# have been in its training set, so that period is **clean**.

# %%
fig, ax = plt.subplots(figsize=(9, 2.2))
for i, w in enumerate(windows.values()):
    ax.barh(i, (w.effective_release - w.test_start).days, left=w.test_start, color="tab:red", alpha=0.5)
    ax.barh(i, (pd.Timestamp(cfg.data.end) - w.clean_start).days, left=w.clean_start, color="tab:green")
ax.set_yticks(range(len(windows)), list(windows)); ax.set_title("red: possibly seen · green: clean");
print("common clean window starts", common_clean_start(windows).date())

# %% [markdown]
# ## 2. Labelling a forecast
# A forecast is "seen" only if its **whole** target window ended before release; "clean" if
# it was made ≥ 30 days after release; otherwise it is in the gap and not used.
#
# 🤔 **Predict before you run:** a 20-day target made 2024-11-15 for Chronos-Bolt
# (released 2024-11-26): seen, clean, or gap?

# %%
cb = windows["chronos_bolt_tiny"]
origins = pd.Series(pd.to_datetime(["2019-03-01", "2024-11-15", "2025-02-03"]))
ends = pd.Series(pd.to_datetime(["2019-03-29", "2024-12-13", "2025-03-03"]))
print(cb.label(origins, ends).tolist())

# %% [markdown]
# ## 3. The statistic
# `R_w` = (total TSFM loss) / (total reference loss) in window w; `Δ = ln R_clean − ln R_seen`.
# Memorisation ⇒ relatively better where it saw the data ⇒ **Δ > 0**.
#
# Ratios, not differences: if the clean period is simply more volatile, *both* losses grow and
# the ratio does not move. Let's check with fake losses where the clean period is 3× noisier:

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
# ## 4. Placebo and synthetic control
# Regimes differ in more than scale (e.g. COVID in the seen window). A **placebo** runs the
# same Δ for two *baselines*; neither can memorise, so their Δ shows how much regime alone
# moves the statistic. We only call it "evidence consistent with memorisation" if the TSFM's Δ
# is Holm-significant **and** above the placebo's CI.
#
# The **synthetic control** feeds every model simulated series nobody has seen, where the
# optimal forecast is known: it measures skill without any possibility of recall.
#
# **Limits:** short clean windows (≈ 1 year for TimesFM 2.5) mean low power; a null result
# is "no evidence", not "proof of no contamination"; training corpora are only partly
# documented (see the tags in `docs/PRETRAINING-DATA.md`).
#
# ## ✅ Checkpoint
# Write `my_delta(m_seen, ref_seen, m_clean, ref_clean)` returning Δ (NumPy arrays of losses).

# %% tags=["exercise"]
def my_delta(m_seen, ref_seen, m_clean, ref_clean):
    # YOUR CODE HERE
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(my_delta)

# %% [markdown] tags=["after-flashcards"]
# **Next:** open `lessons/09-reading-results/lesson.ipynb` (reading and critiquing our own
# results). Tick lesson 08 in `lessons/PROGRESS.md`.
