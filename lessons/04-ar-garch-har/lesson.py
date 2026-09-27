# %% [markdown]
# # Lesson 04: AR, GARCH and HAR by hand
# ⏱ **90 min** · code you will read: `src/tsfm_rc/models/baselines.py`
#
# **You'll be able to…**
# 1. fit AR(p) with least squares and pick p with BIC;
# 2. run the GARCH(1,1) variance recursion yourself and check `arch` recovers the truth;
# 3. build HAR regressors and explain why fitted coefficients look "too small";
# 4. tell a *direct* forecast from an *iterated* one.
#
# **You need:** Lessons 01–03.

# %%
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tsfm_rc.data.provider import FixtureProvider
from tsfm_rc.data.synthetic import GarchSpec, garch_expected_variance
from tsfm_rc.data.targets import daily_series
from tsfm_rc.models.baselines import GARCH, HAR, ar_bic_select
from tsfm_rc.models.features import har_design
from tsfm_rc.paths import FIXTURE_DIR

manifest = json.loads((FIXTURE_DIR / "MANIFEST.json").read_text())
fx = FixtureProvider(FIXTURE_DIR / "synthetic_ohlcv.csv")
latent = pd.read_csv(FIXTURE_DIR / "synthetic_latent.csv", parse_dates=["date"])

# %% [markdown]
# ## 1. AR(p) and BIC
# AR(2): `x_t = 0.5 x_{t-1} − 0.3 x_{t-2} + noise`. BIC = `n ln(RSS/n) + k ln n`: fit improves
# with more lags, the penalty `k ln n` grows.
#
# 🤔 **Predict before you run:** which p in 0…5 will BIC pick?

# %%
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

# %% [markdown]
# ## 2. GARCH(1,1) by hand
# `σ²_{t+1} = ω + α ε_t² + β σ²_t`, with `ε_t = r_t − μ`. Big shock today → higher variance
# tomorrow, fading at rate `α + β`. The fixture `SYN_GARCH_A` was simulated with known
# parameters, so we can check the recursion against the stored truth.

# %%
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

# %% [markdown]
# 🤔 **Predict:** fitting GARCH to 16 years of data, how close will `α + β` get to the truth?

# %%
g = GARCH("rv")
g.fit(d)
mu, omega, alpha, beta, nu = g.params
print(f"fitted alpha={alpha:.3f} beta={beta:.3f} alpha+beta={alpha + beta:.3f}")
print(f"true   alpha={spec['alpha']:.3f} beta={spec['beta']:.3f} alpha+beta={spec['alpha'] + spec['beta']:.3f}")

# %% [markdown]
# Multi-step: expected variance decays geometrically towards the long-run level
# `ω / (1 − α − β)`. The h-step target averages these.

# %%
true_spec = GarchSpec(spec["omega"], spec["alpha"], spec["beta"])
for start in (0.3, 3.0):
    plt.plot(range(1, 61), garch_expected_variance(true_spec, np.array(start), 60), label=f"σ²_(t+1) = {start}")
plt.axhline(true_spec.uncond_var, ls="--", c="k"); plt.xlabel("steps ahead"); plt.legend();

# %% [markdown]
# ## 3. HAR: regress on yesterday, last week, last month
# Direct model for h = 1: `GK_{t+1} = b0 + b_d GK_t + b_w mean5 + b_m mean22`.
#
# 🤔 **Predict:** the true process has b_d = 0.35. Will OLS on *measured* GK give more or less?

# %%
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

# %% [markdown]
# Regressors measured with noise shrink their coefficients towards zero ("errors in
# variables"), and part of the weight moves to the smoother weekly/monthly averages.
#
# **Direct vs iterated:** HAR and LightGBM fit one regression per horizon (direct). AR and
# GARCH fit a one-step model and apply it repeatedly (iterated).
#
# ## ✅ Checkpoint
# Write `my_garch_path(eps, omega, alpha, beta, s0)`: array `s` with `s[0] = s0` and
# `s[t] = omega + alpha*eps[t-1]**2 + beta*s[t-1]`.

# %% tags=["exercise"]
def my_garch_path(eps, omega, alpha, beta, s0):
    # YOUR CODE HERE
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(my_garch_path)

# %% [markdown] tags=["after-flashcards"]
# **Next:** open `lessons/05-foundation-models/lesson.ipynb` (what a foundation model is and
# how it forecasts with zero training). Tick lesson 04 in `lessons/PROGRESS.md`.
