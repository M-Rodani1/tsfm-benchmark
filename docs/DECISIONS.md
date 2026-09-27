# Decision log

Each entry records a judgment call the spec left open, the choice made, and why.
Entries are append-only; a reversed decision gets a new entry that references the old one.
Design decisions that affect results are also fixed in `PREREGISTRATION.md`.

---

### D-001 — One locked Python 3.11 environment, pinned to what `uni2ts` allows (Build 01)
`uni2ts 2.0.0` (Moirai) requires `numpy~=1.26.0`, `scipy~=1.11.3`, `torch<2.5` and
`gluonts~=0.14.3` (which needs `pandas<2.2`). Chronos (`chronos-forecasting 2.3.2`) and
TimesFM (`timesfm 3.0.2`) accept those versions. Rather than maintaining separate
environments per model (which would make "one command reproduces everything" fragile for
a beginner), the whole project is resolved into **one** `uv.lock` in which all packages,
including the core numerics, use the versions Moirai tolerates (numpy 1.26.4, pandas
2.1.4, scipy 1.11.4, torch 2.4.1). The TSFM packages are an optional extra (`tsfm`) so CI
and tests run without PyTorch, but the core versions are identical with or without the
extra. `requires-python = "==3.11.*"` because 3.11 is the newest version all three TSFM
packages and their pins support together.

### D-002 — Network access in the build environment (Build 01)
In the environment where this repository was built, the egress policy blocked
`huggingface.co` (model weights), `query1.finance.yahoo.com`, `stooq.com`, Tiingo,
Alpha Vantage and `arxiv.org`. PyPI and GitHub were reachable. Consequences, applied
consistently: (1) no market data or model outputs were fabricated; (2) the pipeline is
built and tested on committed synthetic fixtures with known parameters; (3) all three TSFMs
are reported `UNAVAILABLE` for runs made here; (4) the exact local commands are in
`README.md` and `docs/BUILD-REPORT.md`. The TSFM *packages* were installed from PyPI,
so the wrappers are tested against the real library APIs (with randomly initialised
weights in tests only; see D-021 once written).

### D-003 — Universe and survivorship bias (Build 01, pre-registered)
Five liquid ETFs spanning US large/tech/small caps, long Treasuries and gold, plus 21 US
large caps chosen as roughly two per GICS sector among companies listed before 2000 with
long, continuous Yahoo histories and no recent spin-offs that would complicate the
adjusted price series (e.g. GE, MMM and HON were avoided for this reason; LIN for its
2018 merger/ticker change). Real Estate is not represented (no large REIT with a clean
pre-2000 history was obvious without data access). The list was fixed *before* looking
at any data, which avoids choosing assets on which some model happens to do well, but it
is **not** survivorship-free: it conditions on firms that are large in 2026. For
forecast *comparisons* the bias is second-order (all models see the same assets), but
survivors may have smoother dynamics than delisted firms, so results may not transfer to
the full cross-section. A point-in-time constituent list (e.g. CRSP) would remove the
bias; it is not freely available.

### D-004 — `huggingface-hub<1.0` constraint (Build 01)
`uni2ts 2.0.0` pins `datasets~=2.17.1`, a release that predates `huggingface-hub` 1.0.
Allowing hub 1.x would pair them untested. The constraint is precautionary: I did not
verify that hub 1.x actually breaks `uni2ts`. It forces `transformers 4.57.6` (instead
of 5.x), which Chronos supports.

### D-005 — Which checkpoint of each TSFM (Build 01, pre-registered)
Spec: smallest official variant by default.
- **Chronos:** `amazon/chronos-bolt-tiny` (9M), smallest Chronos-Bolt. Chronos-2 (Oct
  2025) exists but the spec names Chronos/Chronos-Bolt; Chronos-2 is in `full.yaml`.
- **TimesFM:** `google/timesfm-2.5-200m-pytorch`. The 1.0 checkpoint is also 200M but
  needs the archived `timesfm==1.3.0` package (incompatible API and dependencies). TimesFM
  3.0 (Aug 2026, ~330M) is larger and its weights are under a non-commercial licence.
- **Moirai:** `Salesforce/moirai-1.1-R-small` rather than `moirai-2.0-R-small`. Both are
  "small"; 1.1 was trained on LOTSA, a public corpus that can be inspected for financial
  series, whereas 2.0's corpus includes "internal Salesforce operational data" that
  cannot be audited, which would weaken the contamination analysis. 2.0 is in `full.yaml`.

### D-006 — Garman–Klass rather than Parkinson (Build 01, pre-registered)
Both use daily OHLC. Parkinson (1980) uses only the high–low range; Garman–Klass (1980)
also uses open and close and is more efficient under driftless Brownian motion (relative
efficiency ≈ 7.4 vs ≈ 5.2 against close-to-close squared returns). Both ignore the
overnight gap and both are biased by discrete trading, so the extra efficiency is the
deciding factor. GK is non-negative for valid OHLC because `0.5 − (2 ln 2 − 1) > 0` and
`|ln(C/O)| ≤ ln(H/L)`; it is zero only if H = L, which we treat as missing.

### D-007 — Aligning return-based volatility forecasts with the GK target (Build 01)
EWMA and GARCH forecast the variance of close-to-close returns, which includes the
overnight gap; the GK target does not. Without adjustment these baselines would be biased
upward and look artificially bad under QLIKE and MSE, which would violate "baselines must
be strong". Each such forecast is multiplied by `c = mean(σ²_GK)/mean(r²)` over the
training window (past data only). This is a one-parameter, leakage-free calibration.

### D-008 — Volatility target is the mean daily variance over h (Build 01)
Using the mean rather than the sum keeps units comparable across horizons (%² per day).
Variance rather than volatility (its square root) because QLIKE and MSE are robust to a
noisy but conditionally unbiased variance proxy (Patton 2011); that robustness does not
hold for volatility.

### D-009 — TSFM volatility input in logs with a lognormal mean correction (Build 01)
Daily GK variance is extremely right-skewed. TSFMs predict medians, but QLIKE/MSE are
minimised by the conditional *mean*. Feeding raw variance and taking the median would bias
TSFM forecasts downward for a known, fixable reason (making them look worse than they
are). Feeding the log and converting each step with `exp(m + s²/2)` uses only the model's
own quantiles and the well-documented near-normality of log realised variance. The same
rule applies to every TSFM. A "level input" variant is a possible extension, not run.

### D-010 — Context length 512 for every TSFM (Build 01)
512 trading days ≈ 2 years covers several volatility regimes, is within every model's
supported context, and keeps CPU cost low. Using each model's maximum instead would
confound "model" with "information set". 2048 is in `full.yaml`.

### D-011 — Test start 2015, stride 5, min 1000 observations, fixed end (Build 01)
Starting in 2015 leaves ≥ 15 years of training data for the ETFs and ≈ 10 years of
"possibly seen" period before the first TSFM release, while clean windows run from the
release to 2026-09-25. Stride 5 (weekly) gives ≈ 590 origins per asset and keeps TSFM
inference affordable on CPU; overlapping 20-day targets are handled by HAC. The end date
is fixed so the study does not change as new data arrive.

### D-012 — CRPS from quantiles, h = 1 only (Build 01)
All three TSFMs expose (or can produce) the nine deciles. CRPS is approximated as twice the
mean pinball loss over these levels (a truncated quantile approximation; it ignores the
tails beyond 10%/90%, identically for every model). For h > 1 the target is a sum/mean of
future values, and quantiles of a sum cannot be recovered from per-step quantiles without
a dependence assumption, so probabilistic evaluation is restricted to h = 1.

### D-013 — HAC lag rule and HLN with an effective horizon (Build 01)
With stride 5, a 20-day target overlaps the next three origins' targets, so forecast
errors are MA(3) in origin units: `q_h = ⌈h/stride⌉ − 1` (0, 0, 3 for h = 1, 5, 20).
Volatility clustering also makes *loss differentials* autocorrelated even without overlap,
so the lag is the larger of `q_h` and the Newey–West (1994) rule of thumb. HLN's
small-sample factor is applied with `k = q_h + 1`, the horizon measured in sampling units.

### D-014 — Pooling with pre-test normalisation (Build 01)
Raw MSEs differ hugely across assets (a 20-day return on AMZN vs TLT); averaging them would
let a few volatile assets dominate. Dividing by a scale computed **before the first test
origin** gives each asset comparable weight without using test-period information.
QLIKE is already scale-free. The cross-sectional mean differential is then tested with
DM-HLN, which accounts for cross-asset correlation because the averaging happens first.

### D-015 — Contamination windows defined by label end vs release date (Build 01)
Pretraining cutoffs are mostly undocumented. The only safe statement is that data after a
checkpoint's public release cannot be in its pretraining set. "Possibly seen" therefore
means "the whole target period ended before release". A 30-day buffer after release
guards against small date uncertainties (e.g. Moirai 1.1 is documented only as "Jun 2024",
so the last day of June is used). If the resolved checkpoint revision is later than the
release date, the clean window must start after it; this is logged.

### D-016 — Re-fit schedules (Build 01)
Re-fitting GARCH at all ~15,000 (asset, origin) pairs × 2 windows is feasible but slow on a
laptop; monthly re-fits with daily filtering are standard practice and lose little.
LightGBM is re-fit yearly. These are fixed before any result is seen.

### D-017 — MCS and bootstrap block length (Build 01)
Block length `max(⌈T^{1/3}⌉, 2(q_h+1))`: the `T^{1/3}` rate is the MSE-optimal order for
block bootstraps of a mean (Hall, Horowitz & Jing 1995), and the floor keeps overlapping
targets within a block. A fixed rule avoids yet another estimated tuning parameter.

### D-018 — Returns in percent (Build 01)
`100·ln(C_t/C_{t-1})` improves the numerical conditioning of GARCH optimisation (as the
`arch` documentation recommends) and makes variances readable (%² per day).

### D-019 — Economic evaluation design (Build 01)
Vol targeting on SPY: every 5 trading days, weight `w = min(2, σ* / σ̂)` with
`σ* = 10%` annualised and `σ̂ = sqrt(252 · ŷ^rv_{t,5})`; cash earns 0; costs 5 bp per
unit of turnover. Because GK excludes the overnight gap, realised volatility will be above
the target for every model; the comparison across models is what matters. Illustrative only.

### D-020 — Lessons authored as `.py` and built into `.ipynb` (Build 01)
Notebook JSON is hard to review and diff. Each lesson's source is a percent-format Python
file (`lesson.py`) that `lessons/_tools/build_notebooks.py` turns into `lesson.ipynb`. A
test fails if the two drift apart, and CI executes every notebook with its solution.

### D-021 — Synthetic fixtures (Build 02)
Five synthetic tickers (2010-01-04 to 2026-06-30, US-federal-holiday business-day calendar as
an approximation of the NYSE calendar) are committed in `data/fixtures/` with a manifest of
SHA-256 hashes and generating parameters: two GARCH(1,1) and two HAR-type (multiplicative
error, levels) variance processes, plus `SYN_QUIRKS` (GARCH) which carries quarterly dividends
and one instance of every data problem the cleaning rules handle. Prices follow a Brownian
path within each day (390 steps, open = previous close), so OHLC and Garman–Klass are
internally consistent and the true variance is stored in `synthetic_latent.csv`. Log volume is
a two-component AR process with a day-of-week effect, **independent of volatility** (a
simplification: real volume and volatility are correlated). A test regenerates the fixtures
from the seed and compares them with the committed files.

### D-022 — Provider details (Build 02)
`yfinance` is called with `auto_adjust=False, actions=True, repair=False`: we want Yahoo's
split-adjusted OHLC plus the separate split/dividend-adjusted close, and we do not want the
library to silently "repair" prices (our cleaning logs every change instead). The raw cache
stores exactly what the provider returned (CSV, shortest round-trip float format). When a
ticker has several cached downloads, the earliest is used so that a study does not silently
change when Yahoo revises history. If a ticker cannot be downloaded it is reported as
unavailable and the run continues with the others. A `csv` provider (Yahoo-format files in a
folder) exists as a fallback if `yfinance` breaks.

### D-023 — Missing daily values (Build 02)
A zero high–low range makes GK undefined (logged as `zero_range`); zero volume on a trading
day becomes missing (`zero_volume`). Targets that include such a day are missing and are
dropped from evaluation (counted in the report), never imputed. Model *inputs* forward-fill
the last valid value (a causal operation), because every model needs a complete context.

### D-024 — LightGBM through its native API (Build 03)
`lightgbm.LGBMRegressor` requires scikit-learn, which nothing else needs. The native
`lightgbm.train` API is used with the pre-registered hyper-parameters mapped one-to-one
(`min_child_samples → min_data_in_leaf`, `subsample → bagging_fraction`, etc.), single
thread, `deterministic=True`.

### D-025 — Parallelism and floating-point reproducibility (Build 03)
Tasks (asset × target × window) run in separate processes started with `spawn` (forking a
process after LightGBM's OpenMP threads exist can deadlock; this happened during the build)
and with one BLAS/OpenMP thread per worker (otherwise four workers × all-core BLAS threads
made the smoke run 4× slower). Every task derives its own seed from the run seed and its
keys, so results do not depend on scheduling. Results are reproducible to floating-point
tolerance, not necessarily bit-for-bit, across machines, BLAS builds and thread counts
(summation order changes the last digits); the tests compare with `rtol = 1e-5`.

### D-026 — Engine rules for individual assets (Build 03)
One origin schedule is built on the union trading calendar. For each asset an origin is
skipped if the asset has fewer than `min_train_obs` rows up to it, or if its last row is more
than 10 calendar days old (not trading yet / halted). The re-fit counter counts *usable*
origins for that asset. The realised target is looked up at the asset's last row ≤ t.

### D-027 — GARCH optimiser failures (Build 03)
If `arch` does not converge (non-zero convergence flag or non-finite parameters) the previous
parameters are kept. If there are none yet, that origin's forecast falls back to EWMA and the
row is flagged `fallback=ewma`. Flags are counted in the report. None occurred in the smoke run.

### D-028 — HAR details (Build 03)
HAR is the original levels specification (Corsi 2009) estimated by OLS, one direct regression
per horizon, with the forecast floored at 1% of the window's mean GK variance (a level-HAR can
go negative). Log-HAR or WLS would be reasonable alternatives but were not pre-registered.
The seasonal-naive volume model maps future steps to weekdays with a business-day offset,
ignoring holidays (a small approximation affecting a few steps per year).

### D-029 — TSFM APIs verified against installed code (Build 04)
The wrappers were written after reading the installed sources: `chronos-forecasting 2.3.2`
(`BaseChronosPipeline.predict_quantiles` returns quantiles `(B, S, Q)` and a "mean" that is
the median for Bolt), `timesfm 3.0.2` (`TimesFM_2p5_200M_torch`; `forecast` returns
`(B, S, 10)` with channel 0 = mean and 1..9 = deciles; channel 5 is the point forecast),
`uni2ts 2.0.0` (`MoiraiForecast.forward` returns samples `(B, num_samples, S)`). Tests build
tiny randomly initialised instances of the real library models and run them through our
adapters (shapes, determinism, batch invariance, causality). Those random models are used
in tests only; nothing they output is stored or reported. TimesFM is loaded with
`torch_compile=False` (compilation time on CPU outweighs the gain for our batch sizes)
and the flags recommended in its README (`normalize_inputs`, continuous quantile head,
flip invariance, positivity inference, quantile-crossing fix).

### D-030 — Moirai patch size "auto" and its 20 extra observations (Build 04)
Moirai 1.x needs a patch size. Hand-picking one would be a tuning decision; the library's
default `patch_size="auto"` instead selects it by the model's own validation loss on the
last `prediction_length` (= 20) points of the input. The forecast is still conditioned on
the last 512 observations, but the model receives 532 in total. This is a small departure
from "identical context for all TSFMs", made to avoid tuning; it uses only data ≤ t.

### D-031 — Synthetic-control calibration (Build 04)
The synthetic series are calibrated on the economic-evaluation asset (SPY; a fixture ticker
in smoke runs): GARCH(1,1) by Gaussian MLE (the simulator's intraday paths are Gaussian),
HAR by OLS of next-day GK on its 1/5/22-day means. HAR coefficients are clipped at zero and
scaled to persistence ≤ 0.95, and the multiplicative shock s.d. is fixed at 0.5, because
the OLS fit on a noisy proxy cannot identify the latent shock size. GARCH persistence is
capped at 0.99. The calibration uses the full sample of that one asset; this is a choice of
simulation parameters, not a forecast, so it is not a leak.

### D-032 — TSFM forecasts and the two window variants (Build 04)
TSFMs have no training window, so the same forecast is used in both the expanding and the
rolling comparison. For Moirai's sampling, the random seed is derived from the run seed and
the batch number; with a cold cache and a fixed batch size the results are reproducible, and
the cache guarantees identical values on reruns.
