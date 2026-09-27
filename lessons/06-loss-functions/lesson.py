# %% [markdown]
# # Lesson 06: Loss functions, and why QLIKE for volatility
# ⏱ **60 min** · code you will read: `src/tsfm_rc/eval/metrics.py`
#
# **You'll be able to…**
# 1. say which forecast each loss rewards (mean, median, a quantile);
# 2. show why a *noisy* volatility proxy breaks some losses but not QLIKE or MSE;
# 3. explain QLIKE's asymmetry;
# 4. read an out-of-sample R².
#
# **You need:** Lessons 02 and 04.

# %%
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tsfm_rc.eval.metrics import absolute_error, oos_r2, pinball, qlike, squared_error
from tsfm_rc.paths import FIXTURE_DIR

rng = np.random.default_rng(0)

# %% [markdown]
# ## 1. Every loss has a favourite forecast
# Draw right-skewed "variances" and try every constant forecast `f`.
#
# 🤔 **Predict before you run:** which `f` minimises the *absolute* error, the mean or the median?

# %%
y = rng.gamma(2.0, 1.0, 100_000)                       # mean 2, median ~1.68
grid = np.linspace(0.5, 4, 141)
curves = {
    "MSE": [squared_error(y, f).mean() for f in grid],
    "MAE": [absolute_error(y, f).mean() for f in grid],
    "QLIKE": [qlike(y, np.full_like(y, f)).mean() for f in grid],
    "pinball 0.9": [pinball(y, f, 0.9).mean() for f in grid],
}
for k, v in curves.items():
    print(f"{k:12s} best f = {grid[np.argmin(v)]:.2f}")
print(f"mean {y.mean():.2f}, median {np.median(y):.2f}, 90% quantile {np.quantile(y, 0.9):.2f}")

# %% [markdown]
# MSE and QLIKE reward the **mean**, MAE the **median**, pinball(τ) the **τ-quantile**. Our
# vol target is a mean, so we need a loss that rewards the mean.
#
# ## 2. The noisy-proxy problem (Patton 2011)
# We never observe true variance; we score against GK, which is truth × noise. On synthetic
# data we have both, so let's compare two forecasters: **A** = the truth, **B** = 10% too low.
#
# 🤔 **Predict:** scored against the noisy proxy, which loss will wrongly prefer B?

# %%
lat = pd.read_csv(FIXTURE_DIR / "synthetic_latent.csv")
truth = lat.loc[lat.ticker == "SYN_HAR_A", "sigma2"].to_numpy()
proxy = truth * rng.gamma(4, 0.25, len(truth))          # unbiased, noisy (like GK)
A, B = truth, 0.9 * truth
for name, fn in [("MSE", squared_error), ("MAE", absolute_error), ("QLIKE", qlike)]:
    winner = "A" if fn(proxy, A).mean() < fn(proxy, B).mean() else "B"
    print(f"{name:6s} scored on proxy picks {winner}")

# %% [markdown]
# MAE picks the wrong model: it rewards the proxy's *median*, which sits below the true
# variance. MSE and QLIKE stay correct whenever the proxy is unbiased. That is why the study
# uses QLIKE (primary) and MSE for volatility.
#
# ## 3. QLIKE is asymmetric
# `QLIKE(y, f) = y/f − ln(y/f) − 1`.

# %%
f = np.linspace(0.2, 3, 200)
plt.plot(f, qlike(np.ones_like(f), f), label="QLIKE, y = 1")
plt.plot(f, squared_error(1, f), label="squared error")
plt.axvline(1, c="k", ls=":"); plt.ylim(0, 3); plt.xlabel("forecast f"); plt.legend();

# %% [markdown]
# Under-predicting risk (f < y) costs more than over-predicting: a sensible property for risk.
#
# ## 4. Out-of-sample R²
# `1 − MSE(model) / MSE(benchmark)`. Positive = better than the benchmark; negative = worse.
#
# 🤔 **Predict:** with pure-noise returns, is the R² of the *historical mean* vs zero positive?

# %%
r = rng.normal(0.03, 1, 2000)
hist_mean = np.array([r[:t].mean() for t in range(250, 2000)])
print(f"OOS R² = {oos_r2(r[250:], hist_mean, np.zeros_like(hist_mean)):.4f}")

# %% [markdown]
# ## ✅ Checkpoint
# Write `my_qlike(y, f)` for NumPy arrays (normalised form above).

# %% tags=["exercise"]
def my_qlike(y, f):
    # YOUR CODE HERE
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(my_qlike)

# %% [markdown] tags=["after-flashcards"]
# **Next:** open `lessons/07-dm-hac-multiple-testing/lesson.ipynb` (is a difference in loss
# real or luck?). Tick lesson 06 in `lessons/PROGRESS.md`.
