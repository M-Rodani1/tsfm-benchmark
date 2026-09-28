---
id: "03"
title: "Look-ahead bias and walk-forward evaluation"
minutes: 60
objectives:
  - show how a tiny look-ahead leak makes a useless forecast look brilliant;
  - cut data at a forecast origin with `ForecastOrigin`;
  - say which training rows a direct h-step model may use;
  - prove a function is leak-free with the "scramble the future" test.
prerequisites: ["02"]
you_need: "Lesson 02 (or: you can index a pandas Series by date)."
code_to_read: ["src/tsfm_rc/origin.py", "src/tsfm_rc/leakage.py"]
mounts: []
next: "04"
---

## Pure noise

We simulate 1,000 days of returns that are pure noise. Nothing here is predictable, which
makes it the perfect place to catch a cheat.

```python
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
```

## A leak that looks like genius

Signal: "is the 11-day moving average of returns positive?" We use it to guess the sign of
the next return. `center=True` means the average also uses the 5 days *after* each date.

```predict
question: "On pure noise, what hit rate should *any* honest signal get?"
kind: number
answer: 50
tolerance: 3
unit: "%"
explain: "About 50%: a coin flip. Anything clearly above that on noise is a leak."
```

```python
def hit_rate(signal: pd.Series) -> float:
    nxt = r.shift(-1)  # the return we try to predict
    ok = signal.notna() & nxt.notna()
    return float((np.sign(signal[ok]) == np.sign(nxt[ok])).mean())

leaky = r.rolling(11, center=True).mean()   # peeks 5 days ahead
honest = r.rolling(11).mean()               # only past and today
print(f"leaky : {hit_rate(leaky):.1%}")
print(f"honest: {hit_rate(honest):.1%}")
```

The leaky signal "works" only because tomorrow's return is *inside* its average. Real leaks
are subtler, so the study never relies on being careful: it makes leaks structurally
impossible.

## ForecastOrigin: the only way data is cut

```text
  past (allowed)                 origin t   future (forbidden)
  ───────────────────────────────────●──────────────────────
```

```python
o = ForecastOrigin(dates[500])
hist = o.history(r)          # a COPY with index <= t
print(hist.index[-1] == o.timestamp, len(hist))
```

## Direct h-step models: labels must be realised

A direct model learns pairs (features at s, target over s+1 … s+h). At origin t the pair for
row s is usable only if s + h ≤ t: its whole target window is already in the past.

```predict
question: "Origin at position 500, h = 5. How many rows (positions 0 … 500) are usable?"
kind: number
answer: 496
tolerance: 0
explain: "Rows 0 … 495 satisfy s + 5 ≤ 500: that is 496 rows."
```

```python
mask = o.label_available_mask(hist.index, horizon=5)
print(mask.sum(), "usable rows; last usable position =", np.flatnonzero(mask)[-1])
```

## The "scramble the future" test

If a function is causal, replacing every value after t with garbage cannot change its
output. `assert_future_invariant` runs exactly that experiment.

```predict
question: "A forecast that standardises the data with the mean and standard deviation of the *whole* sample, then uses only past values: does it pass?"
options:
  - "Yes, it only uses past values"
  - "No, the scaler saw the future"
answer: 1
explain: "The mean and standard deviation were computed on all data, including the future, so scrambling the future changes the output."
```

```python
def causal_forecast(data, origin):
    return origin.history(data).tail(20).mean()          # mean of the last 20 returns

def leaky_forecast(data, origin):
    z = (data - data.mean()) / data.std()                # scaler fitted on ALL data
    return origin.history(z).tail(20).mean()

assert_future_invariant(causal_forecast, r, o)
print("causal passes; leaky passes?", is_future_invariant(leaky_forecast, r, o))
```

## Walk-forward schedule

Origins every `stride` trading days. Expanding window = everything up to t; rolling = the
last N days. Each bar below is one training window.

```python
origins = make_origin_schedule(dates, test_start=dates[600], stride=100, min_train_obs=300)
fig, ax = plt.subplots(1, 2, figsize=(10, 2.5), sharey=True)
for k, org in enumerate(origins):
    p = dates.get_loc(org.timestamp)
    ax[0].barh(k, p, left=0, color="tab:blue")
    ax[1].barh(k, 300, left=p - 300, color="tab:orange")
    for a in ax:
        a.plot(p, k, "k|", ms=12)
ax[0].set_title("expanding"); ax[1].set_title("rolling (300)"); ax[0].set_ylabel("origin #");
```

## Checkpoint

Write `my_label_mask(n, origin_pos, h)`: a boolean NumPy array of length `n` whose entry `i`
is True when row `i`'s h-step label is fully observed at `origin_pos`. No pandas needed.

```checkpoint
```
