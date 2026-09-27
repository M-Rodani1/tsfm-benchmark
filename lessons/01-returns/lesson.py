# %% [markdown]
# # Lesson 01: Returns, log returns, and why they are hard to forecast
# ⏱ **60 min** · code you will read: `src/tsfm_rc/data/targets.py`
#
# **You'll be able to…**
# 1. compute simple and log returns and say why we use log returns;
# 2. build the h-step return target exactly as the study does;
# 3. show that returns barely autocorrelate but their *size* does;
# 4. estimate how many years of data you need to even detect an average return.
#
# **You need:** basic Python and pandas (`df["col"]`, `.loc`). Data: committed synthetic
# fixtures, so everything runs offline.

# %%
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tsfm_rc.data.provider import FixtureProvider
from tsfm_rc.data.targets import daily_series, make_target
from tsfm_rc.paths import FIXTURE_DIR

raw = FixtureProvider(FIXTURE_DIR / "synthetic_ohlcv.csv").fetch("SYN_GARCH_A", "2010-01-01", "2026-12-31")
daily = daily_series(raw)             # r = 100 * ln(P_t / P_{t-1})
raw["adj_close"].plot(title="SYN_GARCH_A (synthetic!)", figsize=(8, 2.5));

# %% [markdown]
# ## 1. Simple vs log returns
# Simple: `P_t/P_{t-1} - 1`. Log: `ln(P_t/P_{t-1})`.
#
# 🤔 **Predict before you run:** over 5 days, which one adds up *exactly* to the 5-day return?

# %%
p = raw["adj_close"].iloc[:6].to_numpy()
simple = p[1:] / p[:-1] - 1
logr = np.log(p[1:] / p[:-1])
print("5-day simple return :", p[-1] / p[0] - 1)
print("sum of simple       :", simple.sum())
print("5-day log return    :", np.log(p[-1] / p[0]))
print("sum of log          :", logr.sum())

# %% [markdown]
# Log returns add up, so an h-day target is just a sum. We multiply by 100 (percent) to
# keep numbers readable. Here is the study's target, checked by hand for one date:

# %%
y5 = make_target(daily, "returns", 5)
d = daily.index[100]
by_hand = daily["r"].iloc[101:106].sum()   # rows AFTER the origin: 101..105
print(y5.loc[d], by_hand)

# %% [markdown]
# ## 2. Is yesterday informative?
# Autocorrelation at lag k = correlation between `x_t` and `x_{t-k}`. Dashed lines ≈ 95% band
# for "no correlation".
#
# 🤔 **Predict:** which will have visible autocorrelation: returns `r`, or their size `|r|`?

# %%
r = daily["r"].dropna()
lags = range(1, 21)
acf_r = [r.autocorr(k) for k in lags]
acf_abs = [r.abs().autocorr(k) for k in lags]
band = 1.96 / np.sqrt(len(r))
fig, ax = plt.subplots(1, 2, figsize=(10, 2.5), sharey=True)
ax[0].bar(lags, acf_r); ax[0].set_title("ACF of r")
ax[1].bar(lags, acf_abs, color="tab:orange"); ax[1].set_title("ACF of |r|")
for a in ax:
    a.axhline(band, ls="--", c="k"); a.axhline(-band, ls="--", c="k")

# %% [markdown]
# Direction is (nearly) unpredictable; *size* clusters. That is why the study treats
# volatility separately (Lesson 02), and why "forecast zero" is a tough baseline.
#
# ## 3. Signal vs noise
# 🤔 **Predict:** the simulated drift is 0.04% per day (see `data/fixtures/MANIFEST.json`), the
# noise about 1%. How many *years* until the drift is statistically detectable (t-stat of 2)?

# %%
mu, sigma = r.mean(), r.std()
n_days = (2 * sigma / mu) ** 2
print(f"mean {mu:.3f}%/day, sd {sigma:.2f}%  ->  ~{n_days / 252:.0f} years needed")

# %% [markdown]
# Even a model that knows the true drift barely beats "zero" in mean squared error:

# %%
mse_zero = (r**2).mean()
mse_true_mu = ((r - 0.04) ** 2).mean()
print(f"R^2 of the TRUE mean vs zero: {1 - mse_true_mu / mse_zero:.4f}")

# %% [markdown]
# ## ✅ Checkpoint
# Write `my_h_step_return(prices, i, h)`: the percent log return from row `i` to row `i+h`
# (a NumPy array of prices). One line, no loop.

# %% tags=["exercise"]
def my_h_step_return(prices: np.ndarray, i: int, h: int) -> float:
    # YOUR CODE HERE
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(my_h_step_return)

# %% [markdown] tags=["after-flashcards"]
# **Next:** open `lessons/02-volatility/lesson.ipynb` (why volatility *is* forecastable, and
# how to measure it from four prices a day). Tick lesson 01 in `lessons/PROGRESS.md`.
