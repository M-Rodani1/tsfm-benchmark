# GENERATED from site/content/lessons/02-volatility by `make lessons`: edit the source, not this file.

# %% [markdown]
# # Lesson 02: Volatility, and why range estimators work
# ⏱ **60 min** · code you will read: `src/tsfm_rc/data/targets.py (garman_klass_variance)`
#
# **You'll be able to…**
# 1. explain why volatility is forecastable while returns are not;
# 2. compute the Garman–Klass (GK) variance from open, high, low and close;
# 3. show, against a known truth, that GK is a less noisy proxy than squared returns;
# 4. explain the two caveats (discrete trading, the overnight gap).
#
# **You need:** Lesson 01.

# %% [markdown]
# ## Data with a known truth
#
# On real data the true variance is never observed. On synthetic data we know it, so we can
# grade the *proxies* that the study must use instead.

# %%
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tsfm_rc.data.provider import FixtureProvider
from tsfm_rc.data.synthetic import gk_discretisation_factor
from tsfm_rc.data.targets import daily_series, garman_klass_variance, make_target, parkinson_variance
from tsfm_rc.paths import FIXTURE_DIR

T = "SYN_HAR_A"
raw = FixtureProvider(FIXTURE_DIR / "synthetic_ohlcv.csv").fetch(T, "2010-01-01", "2026-12-31")
latent = pd.read_csv(FIXTURE_DIR / "synthetic_latent.csv", parse_dates=["date"])
truth = latent[latent.ticker == T].set_index("date")["sigma2"]  # the TRUE daily variance (%²)
daily = daily_series(raw)
print(daily[["r", "gk"]].describe().round(3))

# %% [markdown]
# ## Volatility comes in clusters
#
# Calm days tend to follow calm days, and turbulent days follow turbulent ones. That is why
# volatility can be forecast while returns cannot. The chart shows sixty days of a simulated
# series from the course fixtures, so its true daily volatility is known. Then a shock hits.
# Before you look at what came next, make your own forecast.
#
# 🤔 **Predict before you run:** Over the next 40 days, volatility will most likely
#
# *(On the website this question comes with a chart of the series; it is drawn from `figures/vol-clusters.json` in the lesson folder of `site/content`.)*
#
# - Snap back to normal within a couple of days
# - Stay high, then fade slowly over several weeks
# - Keep climbing
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **Stay high, then fade slowly over several weeks.** Each day keeps most of yesterday's variance, so a shock fades over weeks, not days. That persistence is what makes volatility forecastable, and it is what the GARCH and HAR baselines of lesson 04 exploit. One path is a single draw, though: judge a forecast over many shocks, as the study does over many days.
#
# </details>

# %% [markdown]
# ## Three ways to measure one day's variance
#
# - squared return `r²` (uses only the close);
# - Parkinson: `ln(H/L)² / (4 ln 2)` (uses the range);
# - Garman–Klass: `0.5 ln(H/L)² − (2 ln 2 − 1) ln(C/O)²` (range + open/close).
#
# 🤔 **Predict before you run:** Which line will hug the true variance most closely?
#
# - r²
# - Parkinson
# - Garman–Klass
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **Garman–Klass.** GK uses the most information from the day (range, open and close): for continuous prices it is about 7× more efficient than r².
#
# </details>

# %%
proxies = pd.DataFrame({
    "r^2": daily["r"] ** 2,
    "Parkinson": parkinson_variance(raw["high"], raw["low"]),
    "GK": daily["gk"],
})
w = slice("2019-01-01", "2019-12-31")
ax = proxies.loc[w].plot(alpha=0.6, figsize=(9, 3), logy=True)
truth.loc[w].plot(ax=ax, c="k", lw=2, label="truth"); ax.legend();

# %% [markdown]
# ## Grade the proxies
#
# A proxy's variance around the truth is its **noise**. Compare the `var` column below.

# %%
ratio = proxies.div(truth, axis=0)
print(pd.DataFrame({"mean(proxy/truth)": ratio.mean(), "var(proxy/truth)": ratio.var()}).round(3))

# %% [markdown]
# ## Caveat A: discrete trading
#
# The recorded high is the highest *trade*, not the highest point of a continuous path, so the
# range is a bit too small. That is why the mean GK ratio above is below 1.
#
# 🤔 **Predict before you run:** With more trades per day, does E[GK]/truth move towards 1 or away from it?
#
# - Towards 1
# - Away from 1
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **Towards 1.** More observations per day catch the true extremes better, so the downward bias shrinks.
#
# </details>

# %%
for steps in (26, 78, 390):
    k = gk_discretisation_factor(steps, n_paths=20_000)
    print(f"{steps:4d} observations per day -> E[GK]/truth = {k:.3f}")

# %% [markdown]
# ## Caveat B: the overnight gap
#
# GK uses only today's O, H, L, C, so a jump between yesterday's close and today's open is
# invisible. In these fixtures `open == previous close`; in real data it isn't, so the study's
# target is *open-to-close* variance (docs/DECISIONS.md, D-006/D-007).

# %%
print("fixture overnight gaps:", float((raw["open"] - raw["close"].shift()).abs().max()))

# %% [markdown]
# ## Averaging over h days cuts noise
#
# 🤔 **Predict before you run:** Is the 20-day average GK closer to the 20-day average truth than the 1-day GK is to the 1-day truth?
#
# - Yes
# - No
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **Yes.** Averaging h noisy measurements shrinks the noise; the truth moves slowly, so it barely changes.
#
# </details>

# %%
for h in (1, 5, 20):
    y = make_target(daily, "rv", h)
    t = truth.rolling(h).mean().shift(-h)
    print(f"h={h:2d}  corr(target, truth) = {y.corr(t):.3f}")

# %% [markdown]
# Volatility *is* forecastable because the truth itself moves slowly: its past says a lot about
# its future. Lesson 04 exploits this with EWMA, GARCH and HAR.

# %% [markdown]
# ## Checkpoint
#
# Write `my_garman_klass(o, h, l, c)` for NumPy arrays, returning the variance in **%²**.

# %% tags=["exercise"]
def my_garman_klass(o, h, l, c):
    # YOUR CODE HERE
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(my_garman_klass)

# %% [markdown] tags=["flashcards"]
# ## Flashcards
#
# Cover the answer, say it out loud, then check. `make flashcards` exports these to Anki; the website schedules them for review.
#
# 1. **Q:** Write the Garman–Klass daily variance estimator.
#    - **A:** 0.5 [ln(H/L)]^2 − (2 ln 2 − 1) [ln(C/O)]^2 (times 100^2 for %^2).
# 2. **Q:** Why is GK always non-negative for valid OHLC?
#    - **A:** |ln(C/O)| ≤ ln(H/L) and 0.5 > 2 ln 2 − 1 ≈ 0.386, so the first term dominates.
# 3. **Q:** Why is volatility forecastable when returns are not?
#    - **A:** Variance moves slowly and clusters, so its past strongly predicts its near future.
# 4. **Q:** What is a volatility "proxy"?
#    - **A:** A noisy but (roughly) unbiased measurement of the unobservable true variance, e.g. r^2 or GK.
# 5. **Q:** Why prefer GK over squared returns as the proxy?
#    - **A:** It uses the intraday range and is several times less noisy (about 7x more efficient in theory).
# 6. **Q:** What does GK miss in real markets?
#    - **A:** The overnight gap between yesterday's close and today's open; it measures open-to-close variance.
# 7. **Q:** Why is GK slightly biased low in practice?
#    - **A:** Trading is discrete, so the recorded high/low understate the true extremes of the price path.
# 8. **Q:** How does the study define the h-day volatility target?
#    - **A:** The mean of the daily GK variance over the next h trading days (%^2 per day).

# %% [markdown] tags=["after-flashcards"]
# **Next:** open `lessons/03-lookahead-walkforward/lesson.ipynb` (Look-ahead bias and walk-forward evaluation). Tick lesson 02 in `lessons/PROGRESS.md`.
