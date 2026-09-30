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
*Update (Audit-01, D-054):* on x86-64 the CLI now pins OpenBLAS's kernels, which makes the
committed artifacts reproducible bit for bit on other x86-64 machines.

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

### D-033 — DM variance rule amended after a size simulation (Build 05)
See PREREGISTRATION.md amendment A2 for the Monte Carlo table. The lesson for the audit:
the original rule looked standard but was wrong for the one horizon with overlap. The
test that found it is kept in the suite, asserting both that the amended rule has
approximately correct size and that the original one does not.

### D-034 — Proxy alignment revised (Build 05, amendment A3)
D-007's `mean(GK)/mean(r²)` was replaced by the QLIKE-optimal `mean(GK_t / s²_t)` using each
model's in-sample one-step variances, after the smoke evaluation showed a single jump day
(r² ≫ GK) can halve the constant. `tests/test_baselines_recovery.py::test_proxy_alignment_robust_to_a_jump_day`
demonstrates both behaviours.

### D-035 — Reports are pure functions of stored artifacts (Build 06)
`reports/<run>/RESULTS.md` and its figures are rendered only from `results/<run>/` (no
statistics are recomputed, no wall-clock time is printed; figure files are written without
timestamps and with a fixed SVG hash salt). A test re-renders the committed smoke report from
the committed artifacts and requires byte equality, so any hand edit or stale report fails CI.
`reports/RESULTS.md` shows the most complete run in the checkout (`default` > `default_fixtures`
> `smoke`) and says which one it is.

### D-036 — Charts encode role, not identity (Build 06)
Model identity is always on an axis label; colour encodes only the role (baseline / TSFM /
oracle) using slots 1–3 of the validated reference palette (all-pairs CVD and normal-vision
checks pass; the aqua slot is < 3:1 contrast, so every mark is labelled and every figure is
accompanied by a table). MCS p-values use a single-hue sequential ramp. Relative losses are
plotted on a linear axis for readability.

### D-037 — Verifying `make reproduce` without network (Build 06)
`configs/default_fixtures.yaml` is the default configuration with only the data block and the
economic-evaluation asset changed (the diff is two blocks). Running it exercises every stage
with the default horizons, windows, stride, re-fit schedule, context length and bootstrap
sizes. `configs/smoke_real.yaml` is a two-ETF real-data smoke run that `make smoke` executes
only if its Yahoo data are already cached.

### D-038 — Dashboard design (Build 07)
One self-contained `reports/dashboard/index.html` (inline CSS and vanilla JavaScript, SVG
charts, no external scripts, fonts or network calls) embeds the stored tables of every run in
`results/`, selectable in a filter row (run, period, window, target, horizon, asset, model).
The page only filters and draws stored numbers; cumulative loss differentials are precomputed
by the evaluation stage (`loss_diff_series.cum_diff`). Per-asset differential series are
stored for the expanding window only, and per-asset DM tests for the common clean window only
(to bound file size); the page says so when a selection has no stored data. Colour follows
the model: the three TSFMs take palette slots 1–3; baselines share slots 4–7 across targets
(no chart ever shows two models with the same slot, because the sharing models never appear
under the same target). The DM/MCS matrix uses a diverging blue–grey–red scale in seven bins
of relative loss with ★ (Holm-significant) and ● (in MCS) as secondary encodings, plus a
table view. Light and dark themes are separately specified token sets; `#dark` / `#light`
in the URL forces one.

### D-039 — Test for the primary family at stride 1: Kiefer–Vogelsang fixed-b (Audit-01, amendment A4)
**Question.** At stride 1, consecutive h-day targets overlap by h − 1 days. Which variance rule
keeps a two-sided 5% DM-type test closest to its nominal size for the sample sizes of the
clean windows (T ≈ 100–540)?
**Design** (`src/tsfm_rc/eval/size_study.py`; re-run by
`tests/test_stats.py::test_a4_size_grid_stride1`).
- *Grid and replications:* T ∈ {100, 250, 450} origins one trading day apart,
  h ∈ {1, 5, 20}, 5,000 replications per cell, seed 20260928. The Monte Carlo standard error
  at 5% is ≈ 0.003.
- *Null processes:* d_t = sum of h daily Gaussian AR(1) contributions with φ ∈ {0, 0.3, 0.6},
  and `garch_sq`, a difference of squared h-day error sums sharing one GARCH(1,1) volatility
  (a heavy-tailed, heteroskedastic MSE differential).
- *Candidates:*
  1. rectangular kernel, lag h − 1, HLN factor, t_{T−1}, falling back to Bartlett when the
     estimate is non-positive;
  2. Bartlett, lag max(h − 1, ⌊4(T/100)^{2/9}⌋), HLN, t_{T−1};
  3. Kiefer–Vogelsang (2002) fixed-b: Bartlett with bandwidth T, no HLN, p-values from the
     exact limiting distribution (`src/tsfm_rc/eval/fixedb.py`);
  4. the Bartlett variance of (2) with fixed-b critical values for its own b = (L + 1)/T,
     simulated under i.i.d. Gaussian data at the same T.
- *Selection rule,* stated before the documented run: the smallest worst-case
  |size − 0.05| over all 36 cells, ties broken by the mean |size − 0.05|. An exploratory run
  with 2,000 replications and another seed gave the same ranking.

**Result: candidate 3, KV fixed-b.** Worst-case error 0.072, mean 0.014, sizes 0.036–0.122.

| test | worst-case size error | mean size error | size range |
|---|---|---|---|
| KV fixed-b | 0.072 | 0.014 | 0.036–0.122 |
| Bartlett + fixed-b critical values | 0.109 | 0.050 | 0.045–0.159 |
| Bartlett | 0.118 | 0.055 | 0.050–0.168 |
| rectangular | 0.281 | 0.053 | 0.046–0.331 |

The rectangular rule fails at h = 1 because its lag is then 0 and ignores any persistence.
Full table (rejection rates at nominal 5%):

| DGP | T | h | rectangular, lag h−1 (+HLN) | (non-positive share) | Bartlett, lag max(h−1, NW) (+HLN) | **KV fixed-b, b = 1** | Bartlett + fixed-b c.v. |
|---|---|---|---|---|---|---|---|
| ar0 | 100 | 1 | 0.051 | 0.000 | 0.061 | **0.051** | 0.045 |
| ar0 | 100 | 5 | 0.064 | 0.000 | 0.110 | **0.060** | 0.105 |
| ar0 | 100 | 20 | 0.152 | 0.005 | 0.159 | **0.114** | 0.150 |
| ar0 | 250 | 1 | 0.053 | 0.000 | 0.056 | **0.048** | 0.052 |
| ar0 | 250 | 5 | 0.057 | 0.000 | 0.112 | **0.056** | 0.113 |
| ar0 | 250 | 20 | 0.088 | 0.000 | 0.127 | **0.074** | 0.120 |
| ar0 | 450 | 1 | 0.051 | 0.000 | 0.056 | **0.057** | 0.052 |
| ar0 | 450 | 5 | 0.052 | 0.000 | 0.096 | **0.051** | 0.094 |
| ar0 | 450 | 20 | 0.068 | 0.000 | 0.118 | **0.062** | 0.114 |
| ar0.3 | 100 | 1 | 0.152 | 0.000 | 0.086 | **0.057** | 0.069 |
| ar0.3 | 100 | 5 | 0.068 | 0.000 | 0.125 | **0.064** | 0.118 |
| ar0.3 | 100 | 20 | 0.144 | 0.007 | 0.148 | **0.111** | 0.139 |
| ar0.3 | 250 | 1 | 0.144 | 0.000 | 0.068 | **0.049** | 0.064 |
| ar0.3 | 250 | 5 | 0.063 | 0.000 | 0.122 | **0.056** | 0.122 |
| ar0.3 | 250 | 20 | 0.089 | 0.000 | 0.131 | **0.075** | 0.125 |
| ar0.3 | 450 | 1 | 0.143 | 0.000 | 0.064 | **0.046** | 0.061 |
| ar0.3 | 450 | 5 | 0.059 | 0.000 | 0.109 | **0.058** | 0.108 |
| ar0.3 | 450 | 20 | 0.070 | 0.000 | 0.120 | **0.061** | 0.115 |
| ar0.6 | 100 | 1 | 0.331 | 0.000 | 0.139 | **0.064** | 0.118 |
| ar0.6 | 100 | 5 | 0.092 | 0.000 | 0.166 | **0.068** | 0.159 |
| ar0.6 | 100 | 20 | 0.158 | 0.006 | 0.168 | **0.122** | 0.156 |
| ar0.6 | 250 | 1 | 0.328 | 0.000 | 0.123 | **0.056** | 0.117 |
| ar0.6 | 250 | 5 | 0.079 | 0.000 | 0.153 | **0.054** | 0.153 |
| ar0.6 | 250 | 20 | 0.085 | 0.000 | 0.130 | **0.079** | 0.124 |
| ar0.6 | 450 | 1 | 0.321 | 0.000 | 0.112 | **0.060** | 0.109 |
| ar0.6 | 450 | 5 | 0.081 | 0.000 | 0.135 | **0.056** | 0.134 |
| ar0.6 | 450 | 20 | 0.076 | 0.000 | 0.126 | **0.063** | 0.120 |
| garch_sq | 100 | 1 | 0.052 | 0.000 | 0.061 | **0.040** | 0.048 |
| garch_sq | 100 | 5 | 0.055 | 0.000 | 0.077 | **0.042** | 0.071 |
| garch_sq | 100 | 20 | 0.122 | 0.029 | 0.079 | **0.060** | 0.073 |
| garch_sq | 250 | 1 | 0.051 | 0.000 | 0.054 | **0.040** | 0.052 |
| garch_sq | 250 | 5 | 0.059 | 0.000 | 0.090 | **0.044** | 0.090 |
| garch_sq | 250 | 20 | 0.072 | 0.003 | 0.081 | **0.043** | 0.075 |
| garch_sq | 450 | 1 | 0.049 | 0.000 | 0.050 | **0.038** | 0.048 |
| garch_sq | 450 | 5 | 0.046 | 0.000 | 0.074 | **0.036** | 0.072 |
| garch_sq | 450 | 20 | 0.060 | 0.000 | 0.086 | **0.048** | 0.080 |

**Power (information, not a selection criterion).** At a mean shift where an infeasible
z-test with the true long-run variance has 80% power (AR(0) and AR(0.3), same grid,
3,000 replications), KV rejected 0.60–0.72 and the other three 0.79–0.91. Part of their
extra rejections is their size distortion. This is the known cost of b = 1. It is accepted
because a wrong-size confirmatory test is worse than a less powerful one, and because stride
1 gives about five times more origins than the stride-5 design, so power overall still
rises.

**Non-positive variance.** The KV variance equals 2T⁻²ΣS_t², a sum of squares. It is zero
only if every d_t is equal; the test is then undefined, reported with p = NaN and flagged
`zero_variance` (never replaced by another rule).

**Residual problem.** At T = 100 and h = 20 the chosen test still rejects up to 12.2%.
Every primary row reports the worst simulated size at the nearest simulated T not above its
own T (`sim_size_max`), and rows with T < 100 stay flagged "small sample".

**Scope.** The stride-5 secondary tests keep the A2 rule, so their tables are unchanged.

### D-040 — Re-fit intervals in the stride-1 primary pass (Audit-01, A4)
PREREGISTRATION §4 gives re-fit intervals "in origins" with their intent in brackets (GARCH
≈ monthly, LightGBM ≈ yearly). At stride 1, "every 4 origins" would re-fit GARCH every 4
trading days: five times more often than in the main pass, which is a different model. The
primary pass therefore keeps the same interval in trading days:
`refit_every(name, cfg, stride) = round(refit_every[name] × evaluation.stride / stride)`,
giving GARCH/GJR every 20 origins and LightGBM every 250 at stride 1. Models without an entry
re-fit at every origin in every pass, because "every origin" means "always use the latest
data", not a fixed number of days. Tested in `tests/test_a4_primary.py`.

### D-041 — How the primary pass is organised (Audit-01, A4)
The stride-1 forecasts are a **separate pass with separate artifacts**:
`forecasts_baselines_primary.parquet`, `forecasts_tsfm_primary.parquet` and
`stats/losses_primary.parquet`. They are not merged into the stride-5 tables.

*Why separate.* Inserting extra origins into the main walk-forward loop would shift every
origin-counted re-fit and change the stride-5 forecasts, so the secondary tables would move.
Keeping the passes apart guarantees the secondary tables are unchanged.

*Which baselines.* The primary pass runs only what the stride-1 analyses need: each target's
reference model and its placebo model, expanding window.

*Where the baselines start.* From the earliest possible clean start (earliest documented
release + 30 days). The A1 effective release can only be later, so every model's actual
window is covered without knowing the weight dates before the baseline stage.

*Where each TSFM starts.* From its own clean start, computed after its weights are resolved.
Origins shared with the stride-5 grid hit the output cache.

*Size.* `losses_primary.parquet` of `default_fixtures` is ignored by git (like `losses.parquet`,
re-derivable).

### D-042 — Proving the secondary tables are unchanged (Audit-01, A4)
`tests/data/pre_a4_table_fingerprints.json` holds per-column SHA-256 fingerprints (row order,
dtype, every cell via `pandas.util.hash_pandas_object`) of every secondary table committed
before A4 (Build 08 artifacts, commit `1433711`). This covers the smoke run's 12 tables and
the `default_fixtures` run's 11; its `losses.parquet` was never committed.
`tests/test_a4_primary.py::test_secondary_tables_unchanged_by_a4` recomputes the fingerprints
of the committed tables and requires the same row count and an identical hash for every
pre-A4 column. Columns added later (for example by Audit-01 fix 3) are allowed. A fingerprint
test was chosen over storing copies of the tables because CI checks out a shallow clone
without history. The same comparison was also done directly with
`pandas.testing.assert_frame_equal` against the Build 08 files when the artifacts were
regenerated (BUILD-REPORT §10).

### D-043 — The website: a static SPA on Netlify (Audit-01 fix 2)
**What.** `site/` is a Vite + React + TypeScript single-page app, deployed as static files
(`netlify.toml`, `docs/DEPLOY.md`). Pages: Home ("Continue"), Lessons, Results, Review, Notes
& log, Research status, Progress & sync.
**Why.**
- *No server of our own.* The site needs no server: Python runs in the browser and progress
  goes to Supabase directly under row-level security.
- *Notebooks and dashboard kept.* The Jupyter track and `reports/dashboard/index.html`
  remain as offline alternatives.
- *Plain React.* No component framework: a small audited dependency set (React, React
  Router, supabase-js, idb, markdown-it; Pyodide is loaded at runtime).

### D-044 — Python in the browser: Pyodide, checked at build time (Audit-01 fix 2)
**Loading.** Pyodide 314.0.7 (Python 3.14) runs in a Web Worker so the page never freezes.
- *Self-hosted core, CDN packages.* The core runtime is served from the site
  (`/pyodide/v314.0.7/`, copied from the pinned npm package). The scientific packages come
  from the matching jsDelivr path (`packageBaseUrl`), integrity-checked against the lock file.
  The site loads NumPy, pandas, SciPy, matplotlib, pydantic, PyYAML and micropip.

**Build-time check** (`site/scripts/pyodide.mjs`). Each of those packages must be in that
release's `pyodide-lock.json`. Every import in lesson code, starters, solutions and checkers
must resolve to Pyodide's own standard library (read from `python_stdlib.zip`), a locked
package, `tsfm_rc` or `checker`. Otherwise the build fails.

**The package.** A pure-Python wheel of `tsfm_rc` is built from `src/` at build time (no
dependencies declared) and installed with `micropip`. Heavy imports (`arch`, `lightgbm`,
`torch`, Hugging Face) were already lazy.

**Where the browser lacks something:**
- *GARCH fitting (lesson 04)* uses `tsfm_rc.models.garch_np`, a NumPy/SciPy re-implementation
  of the `arch` estimator. `tests/test_garch_np.py` shows the same variance path and
  likelihood (to 1e-10) and the same fitted parameters on every fixture.
- *Stored results (lessons 00, 09, 10)* are read through `tsfm_rc.learn.stats_table`: the
  Parquet file locally, the published JSON in the browser (exact floats; `tests/test_publish.py`).
- *Foundation models (lesson 05)* cannot run in a browser; the lesson says so and points to
  the Results page.
- *The GK simulation (lesson 02)* uses fewer paths and steps, stated on the page.

**Verification.**
- *Locally and in CI:* every lesson runs in a browser-like CPython sandbox (only the mounted
  files; `arch`/`lightgbm`/`pyarrow`/`torch` blocked).
- *In CI:* every lesson also runs under Python 3.14 with Pyodide's exact package versions, and
  in real Chromium with Pyodide (Playwright; `REQUIRE_PYODIDE=1`).

### D-045 — One source for the lessons (Audit-01 fix 2)
**Format.** The 11 lessons live in `site/content/lessons/` as Markdown with a small block
syntax (`python`, `predict`, `checkpoint`), plus YAML and Python files for hints, checkers,
solutions, flashcards and error explanations (`site/content/README.md`).

**Generated notebooks.** `lessons/` (notebooks, `lesson.py`, READMEs, checkers, flashcards) is
generated from them by `make lessons`; the tests fail if it is stale.

**Why one source.** Two hand-maintained copies would drift, and an auditor can edit one place.

**Rules enforced by both parsers:**
- a step is at most 150 words of prose between interactive elements, and has something to do;
- 5–10 flashcards and 2–4 tiered hints per lesson;
- a 45–90 minute estimate, and valid prerequisites and `next` links.

### D-046 — Progress storage: local-first, Supabase for one user (Audit-01 fix 2)
**Local first.** Every change goes to IndexedDB immediately (`site/src/lib/db.ts`) and is
synced to Supabase when configured and signed in. The site works offline and with no
Supabase at all (local-only banner).

**Tables** (`site/supabase/migrations/`), all with row-level security:
lesson/step progress (including the last position), exercise attempts (code, pass/fail,
hints, solution viewed, time), drafts, notes, flashcard states, review history and the
session log.

**Access.**
- *Single user.* Magic-link email login; sign-ups disabled after the first login
  (`docs/DEPLOY.md`), with an optional `VITE_ALLOWED_EMAIL` check in the form.
- *Keys.* Only the public anon key is ever in the frontend, and the build refuses a secret
  key.
- *Backup.* Export/import of everything as one JSON file.

### D-047 — Sync conflict rule: last-write-wins per record (Audit-01 fix 2)
**Rule.** Each record carries the client time of its last change (`updated_at`). The newer
record wins.
- *Server side:* the trigger `tsfm_lww()` ignores an update older than the stored row, so a
  stale device cannot overwrite a newer change.
- *Pull:* the client pulls rows changed since its cursor (`server_updated_at`, with a 5 s
  overlap) and keeps a newer dirty local copy.
- *Append-only tables* (attempts, review history) have unique ids and never conflict.
- *Deletions* are tombstones.

**Limitation.** Two devices editing the *same* record offline keep only the later edit; for
flashcards the full review history is still kept, only the card state is last-write-wins.
Clock skew between devices can reorder near-simultaneous edits. Both are acceptable for one
learner.

**Tests.** `site/tests/sync.test.ts` (two simulated devices) and `site/tests/rls.test.ts`
(the trigger on real Postgres).

### D-048 — Spaced repetition: SM-2 (Audit-01 fix 2)
**Choice.** SM-2 (Wozniak 1990) rather than FSRS. It is about 40 auditable lines, is
deterministic, and needs no parameters fitted to a long review history, which one learner
with ~80 cards will not have. Its behaviour is easy to explain: correct answers stretch the
interval by the ease factor, lapses reset it.

**Buttons.** Again / Hard / Good / Easy map to quality 1 / 3 / 4 / 5.

**Cards.** A lesson's cards join the queue (due the same day) when every step of the lesson
is done. The Anki CSV export remains as a secondary option.

**Tests.** `site/tests/srs.test.ts` checks the 1, 6, ⌈6·EF⌉ sequence, the ease formula and
floor, lapses, and that the Anki CSV contains every card in exactly the `make flashcards`
format.

### D-049 — Publishing results to the site (Audit-01 fix 2)
**Command.** `make publish-results` (`src/tsfm_rc/pipeline/publish.py`) exports each run's
stored statistics to `site/public/data/results/<run>/<version>/`:
- the dashboard payload, reusing `reports/dashboard.py`'s selection;
- the lesson tables, with exact round-trip floats;
- a copy of `RESULTS.md`;
- an index with provenance (config hash, data hash, commit), model status, a history, and a
  `SYNTHETIC — not research results` label for fixture runs.

**Versions.** The version is a content hash, so republishing unchanged results changes
nothing.

**What is never published.** Row-level forecasts, losses and raw prices; the site computes
no statistics.

**Home-page task.** Until a real-data run is published, the home page shows the pending
terminal task (`make reproduce`, then `make publish-results` and push). The task is
generated from the published index at build time (`site/scripts/status.mjs`).

### D-050 — Offline support and security headers (Audit-01 fix 2)
**Offline.** A small service worker (`site/public/sw.js`) caches the app shell. It caches
versioned files cache-first (build assets, Pyodide core and packages, the wheel, published
result versions) and fetches everything else network-first. After one visit the site, and
then Python, work offline.

**Headers.** `netlify.toml` sets a strict Content-Security-Policy: scripts only from the site
plus `wasm-unsafe-eval`, and connections only to the site, Supabase and the Pyodide CDN. It
also sets HSTS, `nosniff`, `X-Frame-Options: DENY`, a restrictive Permissions-Policy and
COOP. `vite preview` reads the same headers, so every browser test runs under the production
policy.

### D-051 — How the site is tested (Audit-01 fix 2)
**Unit tests** (Vitest): the scheduler, the sync logic, the IndexedDB store with
export/import, lesson progress, prediction checking and error explanations, the build
scripts (content rules, status parsing, headers, secret-key guard, wheel, Pyodide import
check), and the migrations on a real Postgres (PGlite) proving RLS on every table.

**Browser tests** (Playwright, production build, production headers):
- completing a step;
- a failing then passing exercise with hints;
- progress surviving a reload, and autosave surviving a closed tab;
- reviewing due flashcards;
- export then import;
- the Results page, prerequisite overrides, and offline use.

**Every lesson** (all cells, starter fails, solution passes) runs in real Pyodide. Those
tests need jsDelivr; they are skipped only where it is unreachable (this build container)
and required in CI.

### D-052 — Non-finite loss differentials are counted, not silently dropped (Audit-01 fix 3)
`dm_test` still drops NaN/inf values before computing autocovariances, which joins the
observations on either side of a gap as if they were adjacent. It now appends
`dropped_nonfinite=N` to `DMResult.flag`, combined with any other flag, e.g.
`zero_variance;dropped_nonfinite=1`. The study's own callers align pairs on origins first,
so their series have no gaps and no stored flag changed. A caller that passes a gappy series
now sees it in every table that carries the flag. Tested in
`tests/test_stats.py::test_dm_reports_dropped_nonfinite_values`.

### D-053 — Oracle ratios in the synthetic control carry a bootstrap CI (Audit-01 fix 3)
The synthetic-control table reported ratios like `hist_mean` 0.996× the oracle's loss
without uncertainty, which invites reading "better than optimal". Each ratio now has a 95%
stationary-bootstrap CI (`ratio_to_oracle_lo`/`_hi`). The CI resamples origins of the
per-origin mean losses on paired (series, origin) rows, B = `stats.n_bootstrap`, with the
block length of section 7, and `ratio_ci_covers_1` records whether it contains 1.

The report words a ratio below 1 whose CI covers 1 as "below 1 only by sampling noise" (or
"indistinguishable from the oracle" when it rounds to 1.000). The figure draws the CIs.
Existing columns are unchanged.

### D-054 — OpenBLAS kernels pinned for bit-for-bit reproducibility (Audit-01 fix 3)
**What happened.** Regenerating the fixture artifacts for fix 3 on a new build host changed
the secondary tables, although no forecasting code had changed. The fingerprint test of A4
(D-042) failed.
- *Cause.* The OpenBLAS libraries bundled with the NumPy and SciPy wheels (DYNAMIC_ARCH
  builds) choose a CPU-specific kernel when they load. `arch`'s GARCH optimiser then stops at
  slightly different points within its tolerance.
- *Which kernel made the committed files.* Every committed artifact (Build 08 and fix 1) was
  reproduced exactly with `OPENBLAS_CORETYPE=Prescott`, OpenBLAS's generic x86-64 kernel
  (its fallback when it cannot use AVX). Every forecast table and every stored statistic
  matched, cell by cell. The new host's AVX-512 kernel (and the Haswell, Sandy Bridge and Zen
  kernels) did not.

**Size of the effect,** on the smoke run, native AVX-512 kernel against the committed
Prescott results, rows matched on their keys:
- *Forecasts:* GARCH-family forecasts differ by up to 0.036 (at most 1.6% relative, median
  6 × 10⁻⁶). Every other model differs by at most 3 × 10⁻¹³.
- *DM tests:* p-values move by at most 0.011 and Holm p-values by at most 0.022. No 5%
  decision changes.
- *MCS:* one p-value moves from 0.255 to 1.000, because the best of two near-tied GARCH
  variants swaps. No model enters or leaves a confidence set.

**Decision.** `tsfm-rc` sets `OPENBLAS_CORETYPE=Prescott` on x86-64 before NumPy loads,
unless the variable is already set (`src/tsfm_rc/cli.py`). Every `make` target and CI go
through it.
- *Recorded.* Provenance records the kernel (`openblas_coretype`).
- *Tested.* `tests/test_utils.py::test_cli_pins_openblas_kernel_before_numpy_loads`.
- *Cost.* Negligible: the pipeline's BLAS work is small least-squares problems. The
  foundation models use PyTorch's own libraries, which are unaffected.

**Scope.**
- *Not a change to the study.* No model, statistic or pre-registered choice changes. The pin
  only fixes which of several equally valid floating-point paths is taken.
- *Other hardware.* On ARM machines (e.g. Apple Silicon) the variable is not set. Results
  there agree with the committed ones only to the tolerance above.
- *Other wheels.* Different NumPy/SciPy wheels can still differ; the versions are pinned in
  `uv.lock`.

**Consequence for the analysis.** Near-ties between GARCH variants (and their MCS p-values)
are machine-sensitive at this level. A difference that small is not evidence either way.


### D-055 — The guided journey: one route, one next action (guided-journey fix)
**Problem.** The site had lessons, a "continue" card and a terminal-task card, but nothing
showed the whole route. It did not say in what order to work, how terminal work fits
alongside the lessons, or what "done" means.

**Single source.** `site/content/journey.yaml` defines eight phases, P0 to P7. Each has a
goal, why, time, steps and done criteria. A step is a lesson, a terminal task
(`site/content/tasks/<id>.yaml`) or a site action (tour, Results, review). It is validated at
build time: every lesson and task appears exactly once, all references resolve, goals are one
sentence, and text fields are strings.

**Ordering.**
- *`requires` is a hard dependency only.* P2 needs P1, P5 needs P2, P6 needs P5, and P6–P7
  need real results. Only such a step shows as *locked*.
- *Recommendations live in `nextAction()`.* After lesson 00 it points to P1 and then P2
  right away, because P2 runs for hours unattended. Lessons 01–08 are offered as a secondary
  link while a laptop step waits, and become the next action while the study runs.
- *Lessons are never hard-locked.* A locked lesson page stays usable, with a banner.

**Statuses.** The brief lists done, in progress, next, locked and optional. A sixth,
*upcoming*, was added for a step that is available but not the recommended one. Calling
lesson 03 "locked" while lesson 01 is next would be false.

**Real results** means a published run named `default` (the pre-registered study) whose data
source is Yahoo Finance or CSV. That is `publish.py`'s rule for non-synthetic runs: any other
source is labelled `SYNTHETIC — not research results`. The run must be `default` because
`smoke_real` is also real data but is not the study. When real results exist, P1, P2 and P5
are marked done automatically (`auto: real_results`). This is a build-time fact: it changes
when a push of `site/public/data/results` makes Netlify rebuild.

**How a terminal step is completed,** in order of strength:
1. auto-detected;
2. a pasted output that the site checks (D-056);
3. "I've done this", recorded and shown everywhere as **self-reported**.

The long-running study has a separate *started* state, set by its start button or by pasted
output that shows it running. It drives the "Study running on your laptop?" card.

**Tests.** `site/tests/journey.test.ts` checks `nextAction()` and the statuses for a fresh
user, mid-lesson, after lesson 00, with P2 running, with results published, when pushed but
not yet rebuilt, and when everything is done. It also checks that exactly one step is ever
*next*, the breadcrumbs, and the YAML validation.

### D-056 — Checking pasted terminal output (guided-journey fix)
**Where the markers come from.** `site/src/lib/cliparse.ts` recognises output by strings
copied from the code that prints them:
- `doctor.py`: check lines, `→` fixes and the three summary lines;
- `cli.py`: fetch statuses, `[validate]`, `[report]`, `[dashboard]`, `[publish]`;
- `pipeline/run.py`: `[data]`, `[tsfm] … AVAILABLE|UNAVAILABLE`, `[evaluate]`;
- GNU make and shell messages.

`tests/test_doctor_flashcards.py::test_site_output_markers_match_the_cli` fails if the CLI's
wording drifts away from the parser.

**What counts as success:**
- *Phase 1:* the doctor ran to the end with no ✗, and no ! except the real-data cache, stored
  results, lessons and uv, which are empty or optional before Phase 2.
- *Phase 2:* a finished pipeline run with `[evaluate]`, `[report] …/reports/default/…` and
  `[dashboard]`. A finished run of another config is rejected by name. UNAVAILABLE models are
  accepted but flagged.
- *Phase 5:* the export alone is only progress; the step completes when the site shows the
  real run.
- *Phase 7:* pytest's summary line, with some tests passed and none failed.

A Python traceback is explained with the lesson runner's own `errors.yaml`.

**Privacy.** Only a one-line summary of the check is stored (for example "24 checks:
23 ✓, 1 !, 0 ✗"), never the pasted text, which can contain paths and user names.

**Evidence.** The tests use output captured by running the commands on 2026-09-29
(`site/tests/fixtures/cli/README.md`).
- *Staged:* the Phase 1 success case ran the real doctor against a staged weights cache,
  because Hugging Face is unreachable from the build container.
- *Derived:* the real study and a real publish cannot run there, so those cases are derived
  in the tests from real captures by changing only the run name or label. The tests say so.

### D-057 — Journey state storage (guided-journey fix)
**Table.** A new table, `journey_state`, holds one row per step that has state
(`step_key`, `status` started/done, `method` output/self-reported/site/auto, a short
`detail`, `started_at`, `done_at`). It is local-first in IndexedDB and synced with the same
last-write-wins rule as all progress (D-047). "Reset this step" writes a tombstone.

**Security.** It is added to the one migration file, with RLS identical to the other tables
(the same loop creates its policies and grants). `site/tests/rls.test.ts` checks four
things:
- its four policies and grants equal those of `lesson_progress`;
- users are isolated and the anonymous role has no access;
- re-running the file on a project with data is safe;
- the old seven-table schema upgrades to the new one, keeping its data.

Export and import include the table. Older export files without it still import.

**Browser database versions (added after a defect).** The first release of the journey broke
the site for every browser that had visited it before: a blank page, with "NotFoundError:
One of the specified object stores was not found".
- *Cause.* The browser database `tsfm-rc` was opened with a hard-coded version 1. An existing
  database therefore never ran its upgrade, and the new `journey_state` store did not exist.
- *Fix.* `openStore()` (`site/src/lib/db.ts`) opens the database and, if any store is
  missing, reopens it one version higher so the upgrade creates it. Existing data is kept.
  Nothing hard-codes a version any more, so a later table cannot repeat the mistake.
- *Other tabs.* A tab still running the old site can block the upgrade. The new tab then says
  "Close the other tabs of this site" and starts as soon as they are closed. A tab told that
  a newer version is upgrading closes its connection and asks to be reloaded.
- *Never blank.* A failure while starting now shows a message instead of an empty page.
- *Tests.* Both a unit test and a browser test recreate the old database, with data, before
  the site loads. Both fail on the released code and pass now. A second browser test covers
  the blocking tab.

### D-058 — Journey UI choices (guided-journey fix)
- **The tour** opens automatically only on Home, and only until it is finished or skipped.
  Deep links into a lesson are never redirected. It can be re-opened from *Tour* in the menu.
- **Home** shows one "Do this next" card with one button. A lesson is offered as a text link
  when the next step needs the laptop ("Not at your laptop? …"), because P3–P4 legitimately
  run in parallel with P2.
- **"Next step" at the end of lessons** replaces "Next: lesson NN": after lesson 00 the route
  continues on the laptop, not with lesson 01. When the page is itself the next step, the
  button points at what finishes it: the open lesson step, or the output check.
- **The SYNTHETIC banner** with links to phases 2 and 5 is shown on lessons 09 and 10 (both
  in phases that need real results) and on the Results page. The Phase 6 step "Open the
  Results page" counts only once a real run is published.
- **OS tabs** remember the choice in `localStorage` (a per-browser convenience). They default
  to the visitor's operating system.

### D-059 — The study-console redesign (Direction B)
- **Appearance only.** The redesign changes how the site looks and how its controls behave. It
  does not change the research code, the statistics, what a lesson teaches, or the journey
  logic (`lib/journey.ts` and `nextAction()` are untouched; only their presentation moved).
  Tokens, type and layout: `site/DESIGN.md`.
- **Two additions the comps needed**, both derived from the repository and never typed by hand:
  - `study.json`: `tsfm_rc.pipeline.publish.study_facts`, written by `make publish-results`.
    It holds the models under test, the weights' release dates and the first clean test day
    (config + contamination buffer, the same rule as `contamination.windows`).
  - Lesson 02's chart question (D-060).
- **How Home knows about the laptop.** The site cannot see your laptop, so the study table
  labels every stage by its evidence: *Detected* (a real run is published on this site),
  *Verified from output* (the pasted output passed the check) or *Self-reported*. A study you
  started is only ever self-reported as running. Stages that share one fact show it once.
- **Where progress is saved** is said on Home (Today) and Account, and in the top bar. It is no
  longer a banner on every page. Problems are still shown on every page: a failed sync (with
  *Try again*), offline, or a failed save.
- **Predict**: native radios in a fieldset, a separate "Check" button. The first checked answer
  is stored; "Try again" lets you explore without changing it (it used to be one click to
  answer, with no way back).

### D-060 — Lesson 02's chart question: how its answer is decided
The question "Over the next 40 days, volatility will most likely …" is answered from the
committed fixtures, not by assertion. For every calm-then-shock day of every GARCH series in
the fixtures:
- a calm-then-shock day has a calm previous 60 days (max/median ≤ 1.35) and a shock at least
  1.3 times the calm median;
- the first such day wins, and the next 40 days are skipped;
- nothing after the shock day enters the selection;
- the closest option is the one with the lowest QLIKE (the study's volatility loss) against
  the latent volatility of the next 40 days.

The answer is the option closest most often, pooled over all series. The chart shows the most
recent shock of SYN_GARCH_B.

Result: 73 shocks; the slow fade was closest 45 times, snapping back 23, climbing 5. The slow
fade is also the most frequent in each series on its own, narrowly in SYN_QUIRKS (17 to 16).
The rule was changed twice before this version, both times after seeing a result (BUILD-REPORT
§12.4). That is why it now pools every GARCH series and never looks ahead: no choice of series
or window can decide the answer. `tests/test_lessons.py` recomputes the figure and checks the
answer, the pooling and the per-series plurality.
