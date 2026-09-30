# GENERATED from site/content/lessons/05-foundation-models by `make lessons`: edit the source, not this file.

# %% [markdown]
# # Lesson 05: What a foundation model is, and how zero-shot forecasting works
# ⏱ **60 min** · code you will read: `src/tsfm_rc/models/tsfm.py`
#
# **You'll be able to…**
# 1. explain "pretrained" and "zero-shot" for time series;
# 2. show why scaling and patching let one model read any series;
# 3. turn a model's quantiles into the study's forecasts (and why the median is wrong for variance);
# 4. recognise an `UNAVAILABLE` model and what to do about it.
#
# **You need:** Lessons 02–04.

# %% [markdown]
# ## The idea
#
# A classical model (lesson 04) is *fitted to this asset*. A foundation model is a large
# network trained once on millions of unrelated series (electricity, traffic, web visits,
# synthetic data …). At forecast time it is **not trained on our data at all**: we hand it the
# last 512 values (the *context*) and it returns forecasts. That is "zero-shot".
#
# 🤔 **Predict before you run:** When a foundation model forecasts SPY volatility for this study, how much is it trained on SPY?
#
# - Not at all (zero-shot)
# - Fine-tuned on SPY's history first
# - Re-trained every day
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **Not at all (zero-shot).** The pre-registration fixes zero-shot use: no fine-tuning, the same weights for every asset and date.
#
# </details>

# %% [markdown]
# ## How one network reads any series
#
# Series differ wildly in level. Models first **scale** the context (Chronos divides by mean
# |x|), then cut it into **patches** (Chronos-Bolt: 16 values each) that play the role of words.
#
# 🤔 **Predict before you run:** After scaling, do log volume (≈ 15) and daily returns (≈ ±1) still look different in *level* to the model?
#
# - Yes
# - No, scaling removes the level
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **No, scaling removes the level.** Dividing by mean |x| puts every series on a comparable scale; the network sees shapes.
#
# </details>

# %%
import matplotlib.pyplot as plt
import numpy as np

from tsfm_rc.config import load_config
from tsfm_rc.data.provider import FixtureProvider
from tsfm_rc.data.targets import daily_series
from tsfm_rc.models.tsfm import TSFMUnavailable, load_backend, make_context, to_target_scale
from tsfm_rc.paths import FIXTURE_DIR

d = daily_series(FixtureProvider(FIXTURE_DIR / "synthetic_ohlcv.csv").fetch("SYN_HAR_A", "2010-01-01", "2026-12-31"))
ctx_vol = make_context(d, "volume", 512)
ctx_ret = make_context(d, "returns", 512)
for name, c in [("log volume", ctx_vol), ("returns", ctx_ret)]:
    scaled = c / np.mean(np.abs(c))
    patches = scaled.reshape(-1, 16)          # 32 "tokens" of 16 values
    print(f"{name:10s} raw mean {c.mean():7.2f} | scaled mean {scaled.mean():6.2f} | patches {patches.shape}")

# %% [markdown]
# Whether those shapes carry information about the future is exactly what this study tests.

# %% [markdown]
# ## Loading a real model
#
# If the weights and PyTorch are available, this cell loads Chronos-Bolt tiny and plots a
# forecast. If not, it prints **why**: the study then reports the model as `UNAVAILABLE` and
# never invents numbers.

# %%
cfg = load_config("configs/smoke.yaml")
spec = next(t for t in cfg.models.tsfms if t.name == "chronos_bolt_tiny")
try:
    backend = load_backend(spec, 512, 20)
    med, dec = backend.predict_batch([make_context(d, "rv", 512)], 20)
    plt.plot(np.exp(d["log_gk_in"].iloc[-120:].to_numpy()), label="past GK")
    plt.plot(range(120, 140), np.exp(med[0]), label="median forecast"); plt.legend()
except TSFMUnavailable as e:
    print("UNAVAILABLE:", str(e)[:300])

# %% [markdown]
# ## From quantiles to the study's forecasts
#
# Models output per-step **quantiles** of the input series. For volatility the input is ln(GK).
# `exp(median of ln GK)` is the *median* variance, but QLIKE and MSE reward the *mean*. For a
# lognormal, mean = `exp(m + s²/2)`.
#
# 🤔 **Predict before you run:** Is exp(m) above or below the true mean of exp(X)?
#
# - Above
# - Below
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **Below.** exp is convex, so the mean of exp(X) exceeds exp of the median by the factor exp(s²/2).
#
# </details>

# %%
rng = np.random.default_rng(0)
m, s = np.log(2.0), 0.6
x = np.exp(rng.normal(m, s, 200_000))
print(f"exp(median) = {np.exp(m):.3f}   exp(m + s²/2) = {np.exp(m + s**2 / 2):.3f}   simulated mean = {x.mean():.3f}")

# %% [markdown]
# ## The study's conversion rule
#
# The study reads `m` and `s` off each model's own 10% and 90% quantiles, identically for every
# model (`to_target_scale`, pre-registered in section 5.2). Here it is on a *fake* per-step
# quantile array (not a model output):

# %%
z = np.array([-1.2816, -0.8416, -0.5244, -0.2533, 0, 0.2533, 0.5244, 0.8416, 1.2816])
fake_dec = np.tile(m + s * z, (20, 1))
points, q_h1 = to_target_scale("rv", fake_dec[:, 4], fake_dec, [1, 5, 20])
print(points)

# %% [markdown]
# ## Checkpoint
#
# Write `my_lognormal_mean(median, q10, q90)`: the mean of `exp(X)` when `X` is normal with
# that median and those 10%/90% quantiles. (`1.2816` is the 90% quantile of a standard normal.)

# %% tags=["exercise"]
def my_lognormal_mean(median, q10, q90):
    # YOUR CODE HERE
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(my_lognormal_mean)

# %% [markdown] tags=["flashcards"]
# ## Flashcards
#
# Cover the answer, say it out loud, then check. `make flashcards` exports these to Anki; the website schedules them for review.
#
# 1. **Q:** What does "zero-shot" mean for a time-series foundation model?
#    - **A:** The pretrained model forecasts our series without any training or fine-tuning on it; we only give it a context.
# 2. **Q:** What is the context length in this study?
#    - **A:** 512 past trading days for every TSFM (Moirai additionally uses 20 more for its own patch-size choice).
# 3. **Q:** Why do TSFMs scale the context before using it?
#    - **A:** So one network can read series of any level/unit; it then sees shapes, not magnitudes.
# 4. **Q:** What is a patch in Chronos-Bolt or TimesFM?
#    - **A:** A block of consecutive values (e.g. 16 or 32) treated like one token/word.
# 5. **Q:** Why is exp(median of log variance) a biased variance forecast?
#    - **A:** It is the median of the variance, which is below the mean for a right-skewed (lognormal) distribution.
# 6. **Q:** How does the study convert log-variance quantiles to a variance forecast?
#    - **A:** exp(m + s^2/2) with m = median and s = (q90 − q10)/2.5631, per step, then averaged over h.
# 7. **Q:** What happens if a model's weights cannot be downloaded?
#    - **A:** It is marked UNAVAILABLE everywhere with the reason; no numbers are shown or invented for it.
# 8. **Q:** Name the three TSFMs and their release dates used in the study.
#    - **A:** Chronos-Bolt tiny (2024-11-26), TimesFM 2.5 200M (2025-09-15), Moirai 1.1-R small (June 2024, 2024-06-30 used).

# %% [markdown] tags=["after-flashcards"]
# **Next:** open `lessons/06-loss-functions/lesson.ipynb` (Loss functions, and why QLIKE for volatility). Tick lesson 05 in `lessons/PROGRESS.md`.
