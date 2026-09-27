# %% [markdown]
# # Lesson 02: Volatility, and why range estimators work
# ⏱ **60 min** · code you will read: `garman_klass_variance` in `src/tsfm_rc/data/targets.py`
#
# **You'll be able to…**
# 1. explain why volatility is forecastable while returns are not;
# 2. compute the Garman–Klass (GK) variance from open, high, low, close;
# 3. show (with a known truth) that GK is a less noisy proxy than squared returns;
# 4. explain the two caveats: discrete trading and the overnight gap.
#
# **You need:** Lesson 01.

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

# %% [markdown]
# On real data the true variance is never observed. On synthetic data we know it, so we can
# grade the *proxies*.
#
# ## 1. Three ways to measure one day's variance
# - squared return `r²` (uses only the close);
# - Parkinson: `ln(H/L)² / (4 ln 2)` (uses the range);
# - Garman–Klass: `0.5 ln(H/L)² − (2 ln 2 − 1) ln(C/O)²` (range + open/close).
#
# 🤔 **Predict before you run:** which line will hug the true variance most closely?

# %%
proxies = pd.DataFrame({
    "r^2": daily["r"] ** 2,
    "Parkinson": parkinson_variance(raw["high"], raw["low"]),
    "GK": daily["gk"],
})
w = slice("2019-01-01", "2019-12-31")
ax = proxies.loc[w].plot(alpha=0.6, figsize=(9, 3), logy=True)
truth.loc[w].plot(ax=ax, c="k", lw=2, label="truth"); ax.legend();

# %%
ratio = proxies.div(truth, axis=0)
print(pd.DataFrame({"mean(proxy/truth)": ratio.mean(), "var(proxy/truth)": ratio.var()}).round(3))

# %% [markdown]
# A proxy's variance around the truth is its **noise**: compare the `var` column. Theory
# (Garman & Klass 1980) says GK is ≈ 7× more efficient than `r²` for continuous prices.
#
# ## 2. Caveat A: discrete trading
# The recorded high is the highest *trade*, not the highest point of a continuous path, so the
# range is a bit too small. That is why the mean GK ratio above is below 1:

# %%
for steps in (78, 390, 1950):
    k = gk_discretisation_factor(steps, n_paths=40_000)
    print(f"{steps:5d} observations per day -> E[GK]/truth = {k:.3f}")

# %% [markdown]
# ## 3. Caveat B: the overnight gap
# GK uses only today's O, H, L, C, so a jump between yesterday's close and today's open is
# invisible. In these fixtures `open == previous close`; in real data it isn't, so our
# target is *open-to-close* variance (docs/DECISIONS.md, D-006/D-007).

# %%
print("fixture overnight gaps:", float((raw["open"] - raw["close"].shift()).abs().max()))

# %% [markdown]
# ## 4. Averaging over h days cuts noise
# 🤔 **Predict:** is the 20-day average GK closer to the 20-day average truth than the 1-day?

# %%
for h in (1, 5, 20):
    y = make_target(daily, "rv", h)
    t = truth.rolling(h).mean().shift(-h)
    print(f"h={h:2d}  corr(target, truth) = {y.corr(t):.3f}")

# %% [markdown]
# Why volatility *is* forecastable: the truth itself moves slowly (it clusters), so its past
# says a lot about its future. Lesson 04 exploits this with EWMA, GARCH and HAR.
#
# ## ✅ Checkpoint
# Write `my_garman_klass(o, h, l, c)` for NumPy arrays, returning variance in **%²**.

# %% tags=["exercise"]
def my_garman_klass(o, h, l, c):
    # YOUR CODE HERE
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(my_garman_klass)

# %% [markdown] tags=["after-flashcards"]
# **Next:** open `lessons/03-lookahead-walkforward/lesson.ipynb` (how *not* to cheat when
# evaluating forecasts). Tick lesson 02 in `lessons/PROGRESS.md`.
