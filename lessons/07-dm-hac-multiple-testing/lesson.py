# %% [markdown]
# # Lesson 07: Diebold–Mariano, HAC, and the multiple-testing problem
# ⏱ **90 min** · code you will read: `src/tsfm_rc/eval/dm.py`, `multiple.py`, `mcs.py`
#
# **You'll be able to…**
# 1. test whether two forecasts differ in expected loss (Diebold–Mariano);
# 2. explain why overlapping 20-day targets need a HAC variance, and pick the right one;
# 3. explain why 27 tests at 5% almost guarantee a false "discovery", and fix it with Holm;
# 4. read a Model Confidence Set.
#
# **You need:** Lesson 06.

# %%
import matplotlib.pyplot as plt
import numpy as np

from tsfm_rc.eval.dm import dm_test, long_run_variance
from tsfm_rc.eval.fixedb import kv_critical_value
from tsfm_rc.eval.mcs import model_confidence_set
from tsfm_rc.eval.multiple import holm

rng = np.random.default_rng(0)

# %% [markdown]
# ## 1. The loss differential
# `d_t = L_model,t − L_reference,t`. If E[d] < 0 the model is better. DM is a t-test on the
# mean of d, **but** the standard error must respect autocorrelation in d.
#
# Our origins are 5 days apart and the target spans 20 days, so neighbouring targets share
# 15, 10, 5 days: their errors are correlated.
#
# 🤔 **Predict before you run:** up to which lag will the autocorrelation of d be clearly non-zero?

# %%
def overlapping_diffs(T, rng):
    daily = rng.standard_normal(5 * T + 20)          # daily loss contributions, mean 0
    c = np.cumsum(np.r_[0, daily])
    starts = np.arange(0, 5 * T, 5)
    return c[starts + 20] - c[starts]                # 20-day sums, sampled every 5 days

d = overlapping_diffs(600, rng)
acf = [np.corrcoef(d[k:], d[:-k])[0, 1] for k in range(1, 8)]
plt.bar(range(1, 8), acf); plt.xlabel("lag (origins)"); plt.title("ACF of d");

# %% [markdown]
# ## 2. DM by hand
# `DM = mean(d) / sqrt(Ω/T)`, Ω = long-run variance = γ0 + 2 Σ w_k γ_k. With overlap, the
# study uses w_k = 1 for k = 1..3 (the overlap lags) and the Harvey–Leybourne–Newbold factor.

# %%
T = len(d)
omega = long_run_variance(d, lag=3, kernel="rectangular")
k = 4
by_hand = d.mean() / np.sqrt(omega / T) * np.sqrt((T + 1 - 2 * k + k * (k - 1) / T) / T)
print(f"by hand {by_hand:.4f}   dm_test {dm_test(d, h_eff=4).stat:.4f}")

# %% [markdown]
# ## 3. A real mistake this study made (and fixed)
# The pre-registration first said "Bartlett weights". Bartlett shrinks w_k below 1, so it
# *under*-counts the overlap. Under the null, how often does each version reject at 5%?

# %%
rej = {"bartlett": 0, "rectangular": 0}
for _ in range(400):
    x = overlapping_diffs(150, rng)
    rej["bartlett"] += dm_test(x, h_eff=4, kernel="bartlett", lag=5).pvalue < 0.05
    rej["rectangular"] += dm_test(x, h_eff=4).pvalue < 0.05
print({key: v / 400 for key, v in rej.items()})

# %% [markdown]
# This check is why amendment A2 exists (`docs/PREREGISTRATION.md`). Amendments are allowed;
# silent changes are not.
#
# An audit then found the clean windows too short at stride 5 (≈ 48 origins for TimesFM).
# Amendment A4 uses *every* trading day there, and a bigger simulation picked the
# Kiefer–Vogelsang **fixed-b** test: bandwidth = T, with its own critical value.

# %%
print(f"fixed-b 5% critical value: {kv_critical_value(0.05):.2f} (normal: 1.96)")
print(dm_test(d, h_eff=4, method="kv_b1"))

# %% [markdown]
#
# ## 4. Many tests
# The primary family has 27 tests. If nothing is really different:
#
# 🤔 **Predict:** chance of at least one p < 0.05?

# %%
print(f"theory: {1 - 0.95**27:.2f}")
sims = rng.uniform(size=(10_000, 27))
print(f"simulated, raw p: {(sims.min(1) < 0.05).mean():.2f}")
print(f"simulated, Holm:  {np.mean([holm(p)[1].any() for p in sims[:2000]]):.2f}")

# %% [markdown]
# Holm: sort p-values; compare the smallest with α/27, the next with α/26, …; stop at the
# first failure. It controls the chance of *any* false rejection at 5%.
#
# ## 5. Model Confidence Set
# Instead of pairwise tests, keep every model that cannot be shown worse than the best.

# %%
T = 300
common = rng.gamma(2, 1, T)[:, None]
losses = common + rng.normal(0, 0.3, (T, 4)) + np.array([0.0, 0.02, 0.3, 0.6])
res = model_confidence_set(losses, alpha=0.10, B=500, block=6, rng=rng, names=["A", "B", "C", "D"])
print(res.table())

# %% [markdown]
# ## ✅ Checkpoint
# Write `my_holm(p)`: Holm-adjusted p-values (same order as the input, capped at 1, and
# never decreasing along the sorted order).

# %% tags=["exercise"]
def my_holm(p):
    # YOUR CODE HERE
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(my_holm)

# %% [markdown] tags=["after-flashcards"]
# **Next:** open `lessons/08-contamination/lesson.ipynb` (could the model have seen our test
# data?). Tick lesson 07 in `lessons/PROGRESS.md`.
