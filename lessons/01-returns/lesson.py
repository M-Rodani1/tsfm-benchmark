# GENERATED from site/content/lessons/01-returns by `make lessons`: edit the source, not this file.

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
# **You need:** Basic Python and pandas (`df["col"]`, `.loc`). The data are committed synthetic fixtures.

# %% [markdown]
# ## Load a price series
#
# We load one synthetic asset exactly as the study does. `daily_series` adds the daily return
# `r = 100 · ln(P_t / P_{t−1})` (percent log returns) and the other model inputs.

# %%
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tsfm_rc.data.provider import FixtureProvider
from tsfm_rc.data.targets import daily_series, make_target
from tsfm_rc.paths import FIXTURE_DIR

raw = FixtureProvider(FIXTURE_DIR / "synthetic_ohlcv.csv").fetch("SYN_GARCH_A", "2010-01-01", "2026-12-31")
daily = daily_series(raw)
raw["adj_close"].plot(title="SYN_GARCH_A (synthetic!)", figsize=(8, 2.5));

# %% [markdown]
# ## Simple vs log returns
#
# Simple return: `P_t/P_{t−1} − 1`. Log return: `ln(P_t/P_{t−1})`.
#
# 🤔 **Predict before you run:** Over 5 days, which one adds up *exactly* to the 5-day return?
#
# - Simple returns
# - Log returns
# - Both
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **Log returns.** ln(P5/P0) = ln(P1/P0) + … + ln(P5/P4). Simple returns compound (multiply), they don't add.
#
# </details>

# %%
p = raw["adj_close"].iloc[:6].to_numpy()
simple = p[1:] / p[:-1] - 1
logr = np.log(p[1:] / p[:-1])
print("5-day simple return :", p[-1] / p[0] - 1)
print("sum of simple       :", simple.sum())
print("5-day log return    :", np.log(p[-1] / p[0]))
print("sum of log          :", logr.sum())

# %% [markdown]
# ## The study's h-step target
#
# Log returns add up, so an h-day target is just a sum of the daily returns *after* the
# origin. Here is `make_target`, checked by hand for one date:

# %%
y5 = make_target(daily, "returns", 5)
d = daily.index[100]
by_hand = daily["r"].iloc[101:106].sum()   # rows AFTER the origin: 101..105
print(y5.loc[d], by_hand)

# %% [markdown]
# ## Is yesterday informative?
#
# Autocorrelation at lag k is the correlation between `x_t` and `x_{t−k}`. The dashed lines
# are a rough 95% band for "no correlation".
#
# 🤔 **Predict before you run:** Which will show clear autocorrelation: the returns `r`, or their size `|r|`?
#
# - r
# - |r|
# - Neither
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **|r|.** Direction is (nearly) unpredictable, but big moves cluster: volatility is persistent.
#
# </details>

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
# That is why the study forecasts volatility separately (lesson 02), and why "forecast zero"
# is a tough baseline for returns.

# %% [markdown]
# ## Signal vs noise
#
# The simulated drift is 0.04% per day, the noise about 1%.
#
# 🤔 **Predict before you run:** Roughly how many *years* of daily data until that drift is statistically detectable (t-stat of 2)?
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **10.** n ≈ (2σ/μ)² = (2 × 1 / 0.04)² ≈ 2,500 days ≈ 10 years. The cell below uses the sample mean, which is not exactly 0.04, so it prints a somewhat different number.
#
# </details>

# %%
mu, sigma = r.mean(), r.std()
n_days = (2 * sigma / mu) ** 2
print(f"mean {mu:.3f}%/day, sd {sigma:.2f}%  ->  ~{n_days / 252:.0f} years needed")
mse_zero = (r**2).mean()
mse_true_mu = ((r - 0.04) ** 2).mean()
print(f"R^2 of the TRUE mean vs zero: {1 - mse_true_mu / mse_zero:.4f}")

# %% [markdown]
# Even a model that knows the true drift barely beats "zero" in mean squared error.

# %% [markdown]
# ## Checkpoint
#
# Write `my_h_step_return(prices, i, h)`: the percent log return from row `i` to row `i + h`
# of a NumPy array of prices. One line, no loop.

# %% tags=["exercise"]
def my_h_step_return(prices: np.ndarray, i: int, h: int) -> float:
    # YOUR CODE HERE
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(my_h_step_return)

# %% [markdown] tags=["flashcards"]
# ## Flashcards
#
# Cover the answer, say it out loud, then check. `make flashcards` exports these to Anki; the website schedules them for review.
#
# 1. **Q:** Why use log returns instead of simple returns for multi-day targets?
#    - **A:** Log returns add up over time, so the h-day return is the sum of daily log returns.
# 2. **Q:** How is the daily return defined in this study (units)?
#    - **A:** r_t = 100 * ln(P_t / P_{t-1}), a percent log return from the adjusted close.
# 3. **Q:** Which rows does the h-step target at origin row i use?
#    - **A:** Rows i+1 through i+h (strictly after the origin).
# 4. **Q:** What does autocorrelation at lag k measure?
#    - **A:** The correlation between a series and itself shifted by k periods.
# 5. **Q:** What typically autocorrelates in daily financial data, r or |r|?
#    - **A:** |r| (the size of moves, i.e. volatility clusters); r itself barely does.
# 6. **Q:** Why is "forecast zero" a strong baseline for returns?
#    - **A:** Expected daily returns are tiny compared with their noise, so estimating them adds more error than it removes.
# 7. **Q:** Roughly how many observations are needed to detect a mean mu with noise sigma at t = 2?
#    - **A:** n ≈ (2 sigma / mu)^2; for 0.04% drift and 1% noise that is about 10 years of daily data.

# %% [markdown] tags=["after-flashcards"]
# **Next:** open `lessons/02-volatility/lesson.ipynb` (Volatility, and why range estimators work). Tick lesson 01 in `lessons/PROGRESS.md`.
