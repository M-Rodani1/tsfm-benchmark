---
id: "04"
title: "AR, GARCH and HAR by hand"
minutes: 90
objectives:
  - fit AR(p) with least squares and pick p with BIC;
  - run the GARCH(1,1) variance recursion yourself and recover the true parameters;
  - build HAR regressors and explain why fitted coefficients look "too small";
  - tell a *direct* forecast from an *iterated* one.
prerequisites: ["01", "02", "03"]
you_need: "Lessons 01–03."
code_to_read: ["src/tsfm_rc/models/baselines.py", "src/tsfm_rc/models/garch_np.py"]
mounts: ["fixtures"]
browser_note: "The study fits GARCH with the `arch` package, which does not run in a browser. This lesson uses `tsfm_rc.models.garch_np`, a NumPy/SciPy re-implementation of the same estimator; `tests/test_garch_np.py` proves it gives the same variance path, likelihood and fitted parameters as `arch` on these fixtures."
next: "05"
---

## Setup

The fixtures were simulated from known parameters, stored in `MANIFEST.json`. So in this
lesson every estimate can be checked against the truth.

```python
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tsfm_rc.data.provider import FixtureProvider
from tsfm_rc.data.synthetic import GarchSpec, garch_expected_variance
from tsfm_rc.data.targets import daily_series
from tsfm_rc.models.baselines import HAR, ar_bic_select
from tsfm_rc.models.features import har_design
from tsfm_rc.models.garch_np import fit_garch11_t
from tsfm_rc.paths import FIXTURE_DIR

manifest = json.loads((FIXTURE_DIR / "MANIFEST.json").read_text())
fx = FixtureProvider(FIXTURE_DIR / "synthetic_ohlcv.csv")
latent = pd.read_csv(FIXTURE_DIR / "synthetic_latent.csv", parse_dates=["date"])
print(sorted(manifest["specs"]))
```

## AR(p) and BIC

AR(2): `x_t = 0.5 x_{t−1} − 0.3 x_{t−2} + noise`. BIC = `n ln(RSS/n) + k ln n`: the fit
improves with more lags, but the penalty `k ln n` grows.

```predict
question: "Which p in 0 … 5 will BIC pick?"
kind: number
answer: 2
tolerance: 0
explain: "The true order is 2; with 2,000 observations BIC finds it (extra lags barely lower the RSS but pay ln n each)."
```

```python
rng = np.random.default_rng(0)
x = np.zeros(2000)
for t in range(2, 2000):
    x[t] = 0.5 * x[t - 1] - 0.3 * x[t - 2] + rng.standard_normal()

pmax, n = 5, 2000 - 5
y = x[pmax:]
for p in range(pmax + 1):
    X = np.column_stack([np.ones(n)] + [x[pmax - j : 2000 - j] for j in range(1, p + 1)])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    rss = np.sum((y - X @ beta) ** 2)
    print(p, f"BIC = {n * np.log(rss / n) + (p + 1) * np.log(n):8.1f}", np.round(beta[1:], 2))
print("repo's ar_bic_select picks p =", ar_bic_select(x, pmax)[0])
```

## GARCH(1,1) by hand

`σ²_{t+1} = ω + α ε_t² + β σ²_t`, with `ε_t = r_t − μ`. A big shock today means a higher
variance tomorrow, fading at rate `α + β`. We run the recursion with the true parameters of
`SYN_GARCH_A` and compare with the stored true variance.

```python
spec = manifest["specs"]["SYN_GARCH_A"]["variance"]
print({k: spec[k] for k in ("omega", "alpha", "beta", "mu")})
d = daily_series(fx.fetch("SYN_GARCH_A", "2010-01-01", "2026-12-31"))
truth = latent[latent.ticker == "SYN_GARCH_A"].set_index("date")["sigma2"].iloc[1:]
eps = (d["r"] - spec["mu"]).to_numpy()[1:]   # day 0 has no previous close -> start at day 1
s2 = np.empty(len(eps))
s2[0] = truth.iloc[0]
for t in range(1, len(eps)):
    s2[t] = spec["omega"] + spec["alpha"] * eps[t - 1] ** 2 + spec["beta"] * s2[t - 1]
print("max |hand − truth| =", np.abs(s2 - truth.to_numpy()).max())
```

## Estimating GARCH

Now pretend the parameters are unknown and estimate them by maximum likelihood (Student-t
errors, as in the study).

```predict
question: "With 16 years of daily data, how close will the fitted α + β get to the true 0.98?"
options:
  - "Within about 0.01"
  - "Within about 0.1"
  - "Not close at all"
answer: 0
explain: "Persistence α + β is well identified with thousands of days; α and β separately are less precise."
```

```python
g = fit_garch11_t(d["r"])
print(f"fitted alpha={g.alpha:.3f} beta={g.beta:.3f} alpha+beta={g.alpha + g.beta:.3f}")
print(f"true   alpha={spec['alpha']:.3f} beta={spec['beta']:.3f} alpha+beta={spec['alpha'] + spec['beta']:.3f}")
```

## Multi-step GARCH forecasts

Expected variance decays geometrically towards the long-run level `ω / (1 − α − β)`. The
h-step target averages these expected values.

```python
true_spec = GarchSpec(spec["omega"], spec["alpha"], spec["beta"])
for start in (0.3, 3.0):
    plt.plot(range(1, 61), garch_expected_variance(true_spec, np.array(start), 60), label=f"σ²(t+1) = {start}")
plt.axhline(true_spec.uncond_var, ls="--", c="k"); plt.xlabel("steps ahead"); plt.legend();
```

## HAR: yesterday, last week, last month

Direct model for h = 1: `GK_{t+1} = b0 + b_d GK_t + b_w mean5 + b_m mean22`.

```predict
question: "The true process has b_d = 0.35. Will OLS on *measured* GK give more or less?"
options:
  - "More"
  - "Less"
answer: 1
explain: "Regressors measured with noise shrink their coefficients towards zero (errors in variables); part of the weight moves to the smoother weekly and monthly averages."
```

```python
dh = daily_series(fx.fetch("SYN_HAR_A", "2010-01-01", "2026-12-31"))
X = har_design(np.exp(dh["log_gk_in"]))
target = dh["gk"].shift(-1)                       # next day's GK
ok = X.notna().all(axis=1) & target.notna()
A = np.column_stack([np.ones(ok.sum()), X[ok]])
b_hand, *_ = np.linalg.lstsq(A, target[ok], rcond=None)
har = HAR("rv", horizons=(1,))
har.fit(dh)
print("by hand:", np.round(b_hand, 3), "\nrepo   :", np.round(har.beta[1], 3))
print("truth  :", {k: manifest["specs"]["SYN_HAR_A"]["variance"][k] for k in ("c", "b_d", "b_w", "b_m")})
```

**Direct vs iterated:** HAR and LightGBM fit one regression per horizon (direct). AR and
GARCH fit a one-step model and apply it repeatedly (iterated).

## Checkpoint

Write `my_garch_path(eps, omega, alpha, beta, s0)`: an array `s` with `s[0] = s0` and
`s[t] = omega + alpha*eps[t-1]**2 + beta*s[t-1]`.

```checkpoint
```
