---
id: "06"
title: "Loss functions, and why QLIKE for volatility"
minutes: 60
objectives:
  - say which forecast each loss rewards (mean, median, a quantile);
  - show why a *noisy* volatility proxy breaks some losses but not QLIKE or MSE;
  - explain QLIKE's asymmetry;
  - read an out-of-sample R².
prerequisites: ["02", "04"]
you_need: "Lessons 02 and 04."
code_to_read: ["src/tsfm_rc/eval/metrics.py"]
mounts: ["fixtures"]
next: "07"
---

## Every loss has a favourite forecast

We draw right-skewed "variances" and try every constant forecast `f` against each loss.

```predict
question: "Which constant f minimises the *absolute* error: the mean or the median of y?"
options:
  - "The mean"
  - "The median"
answer: 1
explain: "Absolute error is minimised at the median; squared error at the mean; pinball(τ) at the τ-quantile."
```

```python
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tsfm_rc.eval.metrics import absolute_error, oos_r2, pinball, qlike, squared_error
from tsfm_rc.paths import FIXTURE_DIR

rng = np.random.default_rng(0)
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
```

MSE and QLIKE reward the **mean**, MAE the **median**, pinball(τ) the **τ-quantile**. The
volatility target is a mean, so we need a loss that rewards the mean.

## The noisy-proxy problem

We never observe true variance; we score against GK, which is truth × noise (Patton 2011).
On synthetic data we have both, so compare two forecasters: **A** = the truth, **B** = 10%
too low.

```predict
question: "Scored against the noisy proxy, which loss will wrongly prefer B?"
options:
  - "MSE"
  - "MAE"
  - "QLIKE"
answer: 1
explain: "MAE rewards the proxy's median, which sits below the true variance for a right-skewed proxy."
```

```python
lat = pd.read_csv(FIXTURE_DIR / "synthetic_latent.csv")
truth = lat.loc[lat.ticker == "SYN_HAR_A", "sigma2"].to_numpy()
proxy = truth * rng.gamma(4, 0.25, len(truth))          # unbiased, noisy (like GK)
A, B = truth, 0.9 * truth
for name, fn in [("MSE", squared_error), ("MAE", absolute_error), ("QLIKE", qlike)]:
    winner = "A" if fn(proxy, A).mean() < fn(proxy, B).mean() else "B"
    print(f"{name:6s} scored on proxy picks {winner}")
```

MSE and QLIKE stay correct whenever the proxy is unbiased. That is why the study uses QLIKE
(primary) and MSE for volatility.

## QLIKE is asymmetric

`QLIKE(y, f) = y/f − ln(y/f) − 1`, zero when the forecast is exact.

```python
f = np.linspace(0.2, 3, 200)
plt.plot(f, qlike(np.ones_like(f), f), label="QLIKE, y = 1")
plt.plot(f, squared_error(1, f), label="squared error")
plt.axvline(1, c="k", ls=":"); plt.ylim(0, 3); plt.xlabel("forecast f"); plt.legend();
```

Under-predicting risk (f < y) costs more than over-predicting: a sensible property for risk.

## Out-of-sample R²

`1 − MSE(model) / MSE(benchmark)`. Positive means better than the benchmark; negative, worse.

```predict
question: "Returns with a tiny true mean (0.03) and noise 1: is the R² of the *historical mean* vs zero positive?"
options:
  - "Positive"
  - "Negative"
answer: 1
explain: "Estimating a tiny mean adds more noise than it removes, so the historical mean loses to zero."
```

```python
r = rng.normal(0.03, 1, 2000)
hist_mean = np.array([r[:t].mean() for t in range(250, 2000)])
print(f"OOS R² = {oos_r2(r[250:], hist_mean, np.zeros_like(hist_mean)):.4f}")
```

## Checkpoint

Write `my_qlike(y, f)` for NumPy arrays, in the normalised form above.

```checkpoint
```
