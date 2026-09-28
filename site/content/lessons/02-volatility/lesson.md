---
id: "02"
title: "Volatility, and why range estimators work"
minutes: 60
objectives:
  - explain why volatility is forecastable while returns are not;
  - compute the Garman–Klass (GK) variance from open, high, low and close;
  - show, against a known truth, that GK is a less noisy proxy than squared returns;
  - explain the two caveats (discrete trading, the overnight gap).
prerequisites: ["01"]
you_need: "Lesson 01."
code_to_read: ["src/tsfm_rc/data/targets.py (garman_klass_variance)"]
mounts: ["fixtures"]
browser_note: "The discretisation simulation below uses 20,000 paths and at most 390 steps per day so that it fits in a browser tab; on your computer the study uses 200,000 paths."
next: "03"
---

## Data with a known truth

On real data the true variance is never observed. On synthetic data we know it, so we can
grade the *proxies* that the study must use instead.

```python
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
```

## Three ways to measure one day's variance

- squared return `r²` (uses only the close);
- Parkinson: `ln(H/L)² / (4 ln 2)` (uses the range);
- Garman–Klass: `0.5 ln(H/L)² − (2 ln 2 − 1) ln(C/O)²` (range + open/close).

```predict
question: "Which line will hug the true variance most closely?"
options:
  - "r²"
  - "Parkinson"
  - "Garman–Klass"
answer: 2
explain: "GK uses the most information from the day (range, open and close): for continuous prices it is about 7× more efficient than r²."
```

```python
proxies = pd.DataFrame({
    "r^2": daily["r"] ** 2,
    "Parkinson": parkinson_variance(raw["high"], raw["low"]),
    "GK": daily["gk"],
})
w = slice("2019-01-01", "2019-12-31")
ax = proxies.loc[w].plot(alpha=0.6, figsize=(9, 3), logy=True)
truth.loc[w].plot(ax=ax, c="k", lw=2, label="truth"); ax.legend();
```

## Grade the proxies

A proxy's variance around the truth is its **noise**. Compare the `var` column below.

```python
ratio = proxies.div(truth, axis=0)
print(pd.DataFrame({"mean(proxy/truth)": ratio.mean(), "var(proxy/truth)": ratio.var()}).round(3))
```

## Caveat A: discrete trading

The recorded high is the highest *trade*, not the highest point of a continuous path, so the
range is a bit too small. That is why the mean GK ratio above is below 1.

```predict
question: "With more trades per day, does E[GK]/truth move towards 1 or away from it?"
options:
  - "Towards 1"
  - "Away from 1"
answer: 0
explain: "More observations per day catch the true extremes better, so the downward bias shrinks."
```

```python
for steps in (26, 78, 390):
    k = gk_discretisation_factor(steps, n_paths=20_000)
    print(f"{steps:4d} observations per day -> E[GK]/truth = {k:.3f}")
```

## Caveat B: the overnight gap

GK uses only today's O, H, L, C, so a jump between yesterday's close and today's open is
invisible. In these fixtures `open == previous close`; in real data it isn't, so the study's
target is *open-to-close* variance (docs/DECISIONS.md, D-006/D-007).

```python
print("fixture overnight gaps:", float((raw["open"] - raw["close"].shift()).abs().max()))
```

## Averaging over h days cuts noise

```predict
question: "Is the 20-day average GK closer to the 20-day average truth than the 1-day GK is to the 1-day truth?"
options:
  - "Yes"
  - "No"
answer: 0
explain: "Averaging h noisy measurements shrinks the noise; the truth moves slowly, so it barely changes."
```

```python
for h in (1, 5, 20):
    y = make_target(daily, "rv", h)
    t = truth.rolling(h).mean().shift(-h)
    print(f"h={h:2d}  corr(target, truth) = {y.corr(t):.3f}")
```

Volatility *is* forecastable because the truth itself moves slowly: its past says a lot about
its future. Lesson 04 exploits this with EWMA, GARCH and HAR.

## Checkpoint

Write `my_garman_klass(o, h, l, c)` for NumPy arrays, returning the variance in **%²**.

```checkpoint
```
