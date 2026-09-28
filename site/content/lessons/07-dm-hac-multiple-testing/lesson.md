---
id: "07"
title: "Diebold–Mariano, HAC, and the multiple-testing problem"
minutes: 90
objectives:
  - test whether two forecasts differ in expected loss (Diebold–Mariano);
  - explain why overlapping 20-day targets need a HAC variance, and pick the right one;
  - explain why 27 tests at 5% almost guarantee a false "discovery", and fix it with Holm;
  - read a Model Confidence Set.
prerequisites: ["06"]
you_need: "Lesson 06."
code_to_read: ["src/tsfm_rc/eval/dm.py", "src/tsfm_rc/eval/fixedb.py", "src/tsfm_rc/eval/multiple.py", "src/tsfm_rc/eval/mcs.py"]
mounts: []
next: "08"
---

## The loss differential

`d_t = L_model,t − L_reference,t`. If E[d] < 0 the model is better. DM is a t-test on the
mean of d, **but** its standard error must respect autocorrelation in d. With origins 5 days
apart and 20-day targets, neighbouring targets share 15, 10 and 5 days.

```predict
question: "Up to which lag (in origins) will the autocorrelation of d be clearly non-zero?"
kind: number
answer: 3
tolerance: 0
explain: "Targets 1, 2 and 3 origins apart share 15, 10 and 5 days; 4 apart share none."
```

```python
import matplotlib.pyplot as plt
import numpy as np

from tsfm_rc.eval.dm import dm_test, long_run_variance
from tsfm_rc.eval.fixedb import kv_critical_value
from tsfm_rc.eval.mcs import model_confidence_set
from tsfm_rc.eval.multiple import holm

rng = np.random.default_rng(0)

def overlapping_diffs(T, rng):
    daily = rng.standard_normal(5 * T + 20)          # daily loss contributions, mean 0
    c = np.cumsum(np.r_[0, daily])
    starts = np.arange(0, 5 * T, 5)
    return c[starts + 20] - c[starts]                # 20-day sums, sampled every 5 days

d = overlapping_diffs(600, rng)
acf = [np.corrcoef(d[k:], d[:-k])[0, 1] for k in range(1, 8)]
plt.bar(range(1, 8), acf); plt.xlabel("lag (origins)"); plt.title("ACF of d");
```

## DM by hand

`DM = mean(d) / sqrt(Ω/T)`, where Ω = γ0 + 2 Σ w_k γ_k is the long-run variance. With
overlap, the study uses w_k = 1 for the overlap lags k = 1 … 3 and the Harvey–Leybourne–
Newbold small-sample factor.

```python
T = len(d)
omega = long_run_variance(d, lag=3, kernel="rectangular")
k = 4
by_hand = d.mean() / np.sqrt(omega / T) * np.sqrt((T + 1 - 2 * k + k * (k - 1) / T) / T)
print(f"by hand {by_hand:.4f}   dm_test {dm_test(d, h_eff=4).stat:.4f}")
```

## A real mistake this study made (and fixed)

The pre-registration first said "Bartlett weights". Bartlett shrinks w_k below 1, so it
*under*-counts the overlap.

```predict
question: "Under the null (no real difference), which version rejects more often?"
options:
  - "Bartlett"
  - "Rectangular"
answer: 0
explain: "Under-counting the overlap makes the standard error too small, so Bartlett rejects too often (≈ 9–12% at nominal 5%; the rectangular rule is closer to 5%)."
```

```python
rej = {"bartlett": 0, "rectangular": 0}
for _ in range(400):
    x = overlapping_diffs(150, rng)
    rej["bartlett"] += dm_test(x, h_eff=4, kernel="bartlett", lag=5).pvalue < 0.05
    rej["rectangular"] += dm_test(x, h_eff=4).pvalue < 0.05
print({key: v / 400 for key, v in rej.items()})
```

This check is why amendment A2 exists. Amendments are allowed; silent changes are not.

## Amendment A4: every trading day, and a fixed-b test

An audit found the clean windows too short at stride 5 (≈ 48 origins for TimesFM). A4 uses
*every* trading day there. A bigger simulation then picked the Kiefer–Vogelsang **fixed-b**
test: bandwidth = T, and its own critical value instead of 1.96.

```python
print(f"fixed-b 5% critical value: {kv_critical_value(0.05):.2f} (normal: 1.96)")
print(dm_test(d, h_eff=4, method="kv_b1"))
```

## Many tests

The primary family has 27 tests.

```predict
question: "If nothing is really different, what is the chance of at least one p < 0.05 among 27 independent tests?"
kind: number
answer: 75
tolerance: 5
unit: "%"
explain: "1 − 0.95²⁷ ≈ 0.75: a false 'discovery' is more likely than not."
```

```python
print(f"theory: {1 - 0.95**27:.2f}")
sims = rng.uniform(size=(10_000, 27))
print(f"simulated, raw p: {(sims.min(1) < 0.05).mean():.2f}")
print(f"simulated, Holm:  {np.mean([holm(p)[1].any() for p in sims[:2000]]):.2f}")
```

Holm: sort the p-values; compare the smallest with α/27, the next with α/26, and so on; stop
at the first failure. It controls the chance of *any* false rejection at 5%.

## Model Confidence Set

Instead of pairwise tests, keep every model that cannot be shown worse than the best.

```python
T = 300
common = rng.gamma(2, 1, T)[:, None]
losses = common + rng.normal(0, 0.3, (T, 4)) + np.array([0.0, 0.02, 0.3, 0.6])
res = model_confidence_set(losses, alpha=0.10, B=500, block=6, rng=rng, names=["A", "B", "C", "D"])
print(res.table())
```

## Checkpoint

Write `my_holm(p)`: Holm-adjusted p-values, in the same order as the input, capped at 1, and
never decreasing along the sorted order.

```checkpoint
```
