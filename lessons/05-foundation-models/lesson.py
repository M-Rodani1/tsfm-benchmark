# %% [markdown]
# # Lesson 05: What a foundation model is, and how zero-shot forecasting works
# ⏱ **60 min** · code you will read: `src/tsfm_rc/models/tsfm.py`
#
# **You'll be able to…**
# 1. explain "pretrained" and "zero-shot" for time series;
# 2. show why scaling + patching lets one model read any series;
# 3. turn a model's quantiles into the study's forecasts (and why the median is wrong for variance);
# 4. recognise an `UNAVAILABLE` model and what to do about it.
#
# **You need:** Lessons 02–04.

# %%
import matplotlib.pyplot as plt
import numpy as np

from tsfm_rc.config import load_config
from tsfm_rc.data.provider import FixtureProvider
from tsfm_rc.data.targets import daily_series
from tsfm_rc.models.tsfm import TSFMUnavailable, load_backend, make_context, to_target_scale
from tsfm_rc.paths import FIXTURE_DIR

d = daily_series(FixtureProvider(FIXTURE_DIR / "synthetic_ohlcv.csv").fetch("SYN_HAR_A", "2010-01-01", "2026-12-31"))

# %% [markdown]
# ## 1. The idea
# A classical model (Lesson 04) is *fitted to this asset*. A foundation model is a large
# network trained once on millions of unrelated series (electricity, traffic, web visits,
# synthetic data…). At forecast time it is **not trained on our data at all**: we hand it
# the last 512 values (the *context*) and it returns forecasts. That is "zero-shot".
#
# ## 2. How one network reads any series
# Series differ wildly in level. Models first **scale** the context (Chronos divides by
# mean |x|), then cut it into **patches** (Chronos-Bolt: 16 values each) that play the role
# of words.
#
# 🤔 **Predict before you run:** after scaling, do log volume (≈ 15) and daily returns (≈ ±1)
# still look different to the model?

# %%
ctx_vol = make_context(d, "volume", 512)
ctx_ret = make_context(d, "returns", 512)
for name, c in [("log volume", ctx_vol), ("returns", ctx_ret)]:
    scaled = c / np.mean(np.abs(c))
    patches = scaled.reshape(-1, 16)          # 32 "tokens" of 16 values
    print(f"{name:10s} raw mean {c.mean():7.2f} | scaled mean {scaled.mean():6.2f} | patches {patches.shape}")

# %% [markdown]
# Scaling removes the level, so the network sees *shapes*. Whether those shapes carry
# information about the future is exactly what this study tests.
#
# ## 3. Loading a real model
# If the weights can be downloaded, this cell loads Chronos-Bolt tiny. If not, it prints
# **why**: the study then reports the model as `UNAVAILABLE` and never invents numbers.

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
# ## 4. From quantiles to the study's forecasts
# Models output per-step **quantiles** of the input series. For volatility the input is
# ln(GK). `exp(median of ln GK)` is the *median* variance, but QLIKE and MSE reward the
# *mean*. For a lognormal, mean = `exp(m + s²/2)`.
#
# 🤔 **Predict:** is `exp(m)` above or below the true mean of `exp(X)`?

# %%
rng = np.random.default_rng(0)
m, s = np.log(2.0), 0.6
x = np.exp(rng.normal(m, s, 200_000))
print(f"exp(median) = {np.exp(m):.3f}   exp(m + s²/2) = {np.exp(m + s**2 / 2):.3f}   simulated mean = {x.mean():.3f}")

# %% [markdown]
# The study reads `m` and `s` off each model's own 10% and 90% quantiles, identically for
# every model (`to_target_scale`, pre-registered in section 5.2). Here it is on a fake
# per-step quantile array (not a model output):

# %%
z = np.array([-1.2816, -0.8416, -0.5244, -0.2533, 0, 0.2533, 0.5244, 0.8416, 1.2816])
fake_dec = np.tile(m + s * z, (20, 1))
points, q_h1 = to_target_scale("rv", fake_dec[:, 4], fake_dec, [1, 5, 20])
print(points)

# %% [markdown]
# ## ✅ Checkpoint
# Write `my_lognormal_mean(median, q10, q90)`: the mean of `exp(X)` when `X` has that median
# and 10%/90% quantiles and is normal. (`1.2816` is the 90% quantile of a standard normal.)

# %% tags=["exercise"]
def my_lognormal_mean(median, q10, q90):
    # YOUR CODE HERE
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(my_lognormal_mean)

# %% [markdown] tags=["after-flashcards"]
# **Next:** open `lessons/06-loss-functions/lesson.ipynb` (how we score forecasts, and why
# QLIKE for volatility). Tick lesson 05 in `lessons/PROGRESS.md`.
