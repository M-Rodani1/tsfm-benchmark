# GENERATED from site/content/lessons/07-dm-hac-multiple-testing by `make lessons`: edit the source, not this file.

# %% [markdown]
# # Lesson 07: Diebold–Mariano, HAC, and the multiple-testing problem
# ⏱ **90 min** · code you will read: `src/tsfm_rc/eval/dm.py`, `src/tsfm_rc/eval/fixedb.py`, `src/tsfm_rc/eval/multiple.py`, `src/tsfm_rc/eval/mcs.py`
#
# **You'll be able to…**
# 1. test whether two forecasts differ in expected loss (Diebold–Mariano);
# 2. explain why overlapping 20-day targets need a HAC variance, and pick the right one;
# 3. explain why 27 tests at 5% almost guarantee a false "discovery", and fix it with Holm;
# 4. read a Model Confidence Set.
#
# **You need:** Lesson 06.

# %% [markdown]
# ## The loss differential
#
# `d_t = L_model,t − L_reference,t`. If E[d] < 0 the model is better. DM is a t-test on the
# mean of d, **but** its standard error must respect autocorrelation in d. With origins 5 days
# apart and 20-day targets, neighbouring targets share 15, 10 and 5 days.
#
# 🤔 **Predict before you run:** Up to which lag (in origins) will the autocorrelation of d be clearly non-zero?
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **3.** Targets 1, 2 and 3 origins apart share 15, 10 and 5 days; 4 apart share none.
#
# </details>

# %%
import matplotlib.pyplot as plt
import numpy as np

from tsfm_rc.eval.dm import dm_test, long_run_variance
from tsfm_rc.eval.fixedb import kv_critical_value
from tsfm_rc.eval.mcs import model_confidence_set
from tsfm_rc.eval.multiple import holm

rng = np.random.default_rng(0)

def overlapping_diffs(T, rng):
    daily = rng.standard_normal(5 * T + 20)          # daily loss contributions, mean 0
    c = np.cumsum(np.r_[0, daily])
    starts = np.arange(0, 5 * T, 5)
    return c[starts + 20] - c[starts]                # 20-day sums, sampled every 5 days

d = overlapping_diffs(600, rng)
acf = [np.corrcoef(d[k:], d[:-k])[0, 1] for k in range(1, 8)]
plt.bar(range(1, 8), acf); plt.xlabel("lag (origins)"); plt.title("ACF of d");

# %% [markdown]
# ## DM by hand
#
# `DM = mean(d) / sqrt(Ω/T)`, where Ω = γ0 + 2 Σ w_k γ_k is the long-run variance. With
# overlap, the study uses w_k = 1 for the overlap lags k = 1 … 3 and the Harvey–Leybourne–
# Newbold small-sample factor.

# %%
T = len(d)
omega = long_run_variance(d, lag=3, kernel="rectangular")
k = 4
by_hand = d.mean() / np.sqrt(omega / T) * np.sqrt((T + 1 - 2 * k + k * (k - 1) / T) / T)
print(f"by hand {by_hand:.4f}   dm_test {dm_test(d, h_eff=4).stat:.4f}")

# %% [markdown]
# ## A real mistake this study made (and fixed)
#
# The pre-registration first said "Bartlett weights". Bartlett shrinks w_k below 1, so it
# *under*-counts the overlap.
#
# 🤔 **Predict before you run:** Under the null (no real difference), which version rejects more often?
#
# - Bartlett
# - Rectangular
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **Bartlett.** Under-counting the overlap makes the standard error too small, so Bartlett rejects too often (≈ 9–12% at nominal 5%; the rectangular rule is closer to 5%).
#
# </details>

# %%
rej = {"bartlett": 0, "rectangular": 0}
for _ in range(400):
    x = overlapping_diffs(150, rng)
    rej["bartlett"] += dm_test(x, h_eff=4, kernel="bartlett", lag=5).pvalue < 0.05
    rej["rectangular"] += dm_test(x, h_eff=4).pvalue < 0.05
print({key: v / 400 for key, v in rej.items()})

# %% [markdown]
# This check is why amendment A2 exists. Amendments are allowed; silent changes are not.

# %% [markdown]
# ## Amendment A4: every trading day, and a fixed-b test
#
# An audit found the clean windows too short at stride 5 (≈ 48 origins for TimesFM). A4 uses
# *every* trading day there. A bigger simulation then picked the Kiefer–Vogelsang **fixed-b**
# test: bandwidth = T, and its own critical value instead of 1.96.

# %%
print(f"fixed-b 5% critical value: {kv_critical_value(0.05):.2f} (normal: 1.96)")
print(dm_test(d, h_eff=4, method="kv_b1"))

# %% [markdown]
# ## Many tests
#
# The primary family has 27 tests.
#
# 🤔 **Predict before you run:** If nothing is really different, what is the chance of at least one p < 0.05 among 27 independent tests?
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **75%.** 1 − 0.95²⁷ ≈ 0.75: a false 'discovery' is more likely than not.
#
# </details>

# %%
print(f"theory: {1 - 0.95**27:.2f}")
sims = rng.uniform(size=(10_000, 27))
print(f"simulated, raw p: {(sims.min(1) < 0.05).mean():.2f}")
print(f"simulated, Holm:  {np.mean([holm(p)[1].any() for p in sims[:2000]]):.2f}")

# %% [markdown]
# Holm: sort the p-values; compare the smallest with α/27, the next with α/26, and so on; stop
# at the first failure. It controls the chance of *any* false rejection at 5%.

# %% [markdown]
# ## Model Confidence Set
#
# Instead of pairwise tests, keep every model that cannot be shown worse than the best.

# %%
T = 300
common = rng.gamma(2, 1, T)[:, None]
losses = common + rng.normal(0, 0.3, (T, 4)) + np.array([0.0, 0.02, 0.3, 0.6])
res = model_confidence_set(losses, alpha=0.10, B=500, block=6, rng=rng, names=["A", "B", "C", "D"])
print(res.table())

# %% [markdown]
# ## Checkpoint
#
# Write `my_holm(p)`: Holm-adjusted p-values, in the same order as the input, capped at 1, and
# never decreasing along the sorted order.

# %% tags=["exercise"]
def my_holm(p):
    # YOUR CODE HERE
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(my_holm)

# %% [markdown] tags=["flashcards"]
# ## Flashcards
#
# Cover the answer, say it out loud, then check. `make flashcards` exports these to Anki; the website schedules them for review.
#
# 1. **Q:** What is the Diebold–Mariano test testing?
#    - **A:** H0 that two forecasts have equal expected loss, using the mean of the loss differential d_t and a HAC standard error.
# 2. **Q:** Why are 20-day forecast errors at 5-day origins autocorrelated?
#    - **A:** Consecutive targets overlap by 15, 10 and 5 days, so their errors share shocks (MA(3) in origin units).
# 3. **Q:** What is a long-run (HAC) variance?
#    - **A:** gamma_0 + 2 * sum of weighted autocovariances; the variance of a sample mean when observations are correlated.
# 4. **Q:** Why did the study switch from Bartlett to rectangular weights for h = 20 (amendment A2)?
#    - **A:** Bartlett weights shrink the overlap autocovariances, under-estimating the variance; a simulation showed ~9-12% false rejections at nominal 5%.
# 5. **Q:** What does the Harvey–Leybourne–Newbold correction do?
#    - **A:** Scales the DM statistic for small samples and uses a t distribution with T−1 degrees of freedom.
# 6. **Q:** With 27 independent tests at 5% and no real effects, what is P(at least one rejection)?
#    - **A:** 1 − 0.95^27 ≈ 0.75.
# 7. **Q:** How does the Holm procedure work?
#    - **A:** Sort p-values; compare the k-th smallest with alpha/(m − k + 1); reject until the first failure. Controls family-wise error.
# 8. **Q:** What is a Model Confidence Set?
#    - **A:** The set of models that cannot be rejected as not-best at confidence 1 − alpha, found by sequential elimination.

# %% [markdown] tags=["after-flashcards"]
# **Next:** open `lessons/08-contamination/lesson.ipynb` (Contamination, and how our test works). Tick lesson 07 in `lessons/PROGRESS.md`.
