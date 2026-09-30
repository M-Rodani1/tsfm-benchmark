# GENERATED from site/content/lessons/03-lookahead-walkforward by `make lessons`: edit the source, not this file.

# %% [markdown]
# # Lesson 03: Look-ahead bias and walk-forward evaluation
# ⏱ **60 min** · code you will read: `src/tsfm_rc/origin.py`, `src/tsfm_rc/leakage.py`
#
# **You'll be able to…**
# 1. show how a tiny look-ahead leak makes a useless forecast look brilliant;
# 2. cut data at a forecast origin with `ForecastOrigin`;
# 3. say which training rows a direct h-step model may use;
# 4. prove a function is leak-free with the "scramble the future" test.
#
# **You need:** Lesson 02 (or: you can index a pandas Series by date).

# %% [markdown]
# ## Pure noise
#
# We simulate 1,000 days of returns that are pure noise. Nothing here is predictable, which
# makes it the perfect place to catch a cheat.

# %%
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tsfm_rc.leakage import assert_future_invariant, is_future_invariant
from tsfm_rc.origin import ForecastOrigin, make_origin_schedule

rng = np.random.default_rng(3)
dates = pd.bdate_range("2020-01-01", periods=1000)
r = pd.Series(rng.normal(0, 1, len(dates)), index=dates, name="r")  # pure noise returns
price = 100 * np.exp(r.cumsum() / 100)
price.plot(title="A random walk: nothing here is predictable", figsize=(8, 2.5));

# %% [markdown]
# ## A leak that looks like genius
#
# Signal: "is the 11-day moving average of returns positive?" We use it to guess the sign of
# the next return. `center=True` means the average also uses the 5 days *after* each date.
#
# 🤔 **Predict before you run:** On pure noise, what hit rate should *any* honest signal get?
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **50%.** About 50%: a coin flip. Anything clearly above that on noise is a leak.
#
# </details>

# %%
def hit_rate(signal: pd.Series) -> float:
    nxt = r.shift(-1)  # the return we try to predict
    ok = signal.notna() & nxt.notna()
    return float((np.sign(signal[ok]) == np.sign(nxt[ok])).mean())

leaky = r.rolling(11, center=True).mean()   # peeks 5 days ahead
honest = r.rolling(11).mean()               # only past and today
print(f"leaky : {hit_rate(leaky):.1%}")
print(f"honest: {hit_rate(honest):.1%}")

# %% [markdown]
# The leaky signal "works" only because tomorrow's return is *inside* its average. Real leaks
# are subtler, so the study never relies on being careful: it makes leaks structurally
# impossible.

# %% [markdown]
# ## ForecastOrigin: the only way data is cut
#
# ```text
#   past (allowed)                 origin t   future (forbidden)
#   ───────────────────────────────────●──────────────────────
# ```

# %%
o = ForecastOrigin(dates[500])
hist = o.history(r)          # a COPY with index <= t
print(hist.index[-1] == o.timestamp, len(hist))

# %% [markdown]
# ## Direct h-step models: labels must be realised
#
# A direct model learns pairs (features at s, target over s+1 … s+h). At origin t the pair for
# row s is usable only if s + h ≤ t: its whole target window is already in the past.
#
# 🤔 **Predict before you run:** Origin at position 500, h = 5. How many rows (positions 0 … 500) are usable?
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **496.** Rows 0 … 495 satisfy s + 5 ≤ 500: that is 496 rows.
#
# </details>

# %%
mask = o.label_available_mask(hist.index, horizon=5)
print(mask.sum(), "usable rows; last usable position =", np.flatnonzero(mask)[-1])

# %% [markdown]
# ## The "scramble the future" test
#
# If a function is causal, replacing every value after t with garbage cannot change its
# output. `assert_future_invariant` runs exactly that experiment.
#
# 🤔 **Predict before you run:** A forecast that standardises the data with the mean and standard deviation of the *whole* sample, then uses only past values: does it pass?
#
# - Yes, it only uses past values
# - No, the scaler saw the future
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **No, the scaler saw the future.** The mean and standard deviation were computed on all data, including the future, so scrambling the future changes the output.
#
# </details>

# %%
def causal_forecast(data, origin):
    return origin.history(data).tail(20).mean()          # mean of the last 20 returns

def leaky_forecast(data, origin):
    z = (data - data.mean()) / data.std()                # scaler fitted on ALL data
    return origin.history(z).tail(20).mean()

assert_future_invariant(causal_forecast, r, o)
print("causal passes; leaky passes?", is_future_invariant(leaky_forecast, r, o))

# %% [markdown]
# ## Walk-forward schedule
#
# Origins every `stride` trading days. Expanding window = everything up to t; rolling = the
# last N days. Each bar below is one training window.

# %%
origins = make_origin_schedule(dates, test_start=dates[600], stride=100, min_train_obs=300)
fig, ax = plt.subplots(1, 2, figsize=(10, 2.5), sharey=True)
for k, org in enumerate(origins):
    p = dates.get_loc(org.timestamp)
    ax[0].barh(k, p, left=0, color="tab:blue")
    ax[1].barh(k, 300, left=p - 300, color="tab:orange")
    for a in ax:
        a.plot(p, k, "k|", ms=12)
ax[0].set_title("expanding"); ax[1].set_title("rolling (300)"); ax[0].set_ylabel("origin #");

# %% [markdown]
# ## Checkpoint
#
# Write `my_label_mask(n, origin_pos, h)`: a boolean NumPy array of length `n` whose entry `i`
# is True when row `i`'s h-step label is fully observed at `origin_pos`. No pandas needed.

# %% tags=["exercise"]
def my_label_mask(n: int, origin_pos: int, h: int) -> np.ndarray:
    # YOUR CODE HERE (one line is enough)
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(my_label_mask)

# %% [markdown] tags=["flashcards"]
# ## Flashcards
#
# Cover the answer, say it out loud, then check. `make flashcards` exports these to Anki; the website schedules them for review.
#
# 1. **Q:** What is look-ahead bias?
#    - **A:** Using any information from after the forecast origin t when making (or evaluating the inputs of) a forecast at t.
# 2. **Q:** Why did the centred moving average "predict" pure noise so well?
#    - **A:** With center=True the average at t includes t+1..t+5, so tomorrow's return is part of the signal.
# 3. **Q:** What does ForecastOrigin.history(data) return?
#    - **A:** A copy of data restricted to rows with timestamp <= the origin.
# 4. **Q:** For a direct h-step model at origin position p, which training rows s may be used?
#    - **A:** Only rows with s + h <= p, because their whole label window (s+1..s+h) is already observed.
# 5. **Q:** How does the "scramble the future" test detect a leak?
#    - **A:** It replaces all data after t with garbage; a causal function's output must not change at all.
# 6. **Q:** Expanding vs rolling window?
#    - **A:** Expanding uses all data from the start up to t; rolling uses only the last N observations.
# 7. **Q:** What is the stride of a walk-forward schedule?
#    - **A:** The number of trading days between consecutive forecast origins (5 in this study).
# 8. **Q:** Name a subtle leak that is not about dates in an index.
#    - **A:** Fitting a scaler (mean/std), choosing hyper-parameters, or selecting features on the full sample.

# %% [markdown] tags=["after-flashcards"]
# **Next:** open `lessons/04-ar-garch-har/lesson.ipynb` (AR, GARCH and HAR by hand). Tick lesson 03 in `lessons/PROGRESS.md`.
