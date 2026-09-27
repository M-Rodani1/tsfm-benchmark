# Build report: TSFM Reality Check

Hand-off document for the owner and for an independent auditor. It says what was built,
what was actually run, what could not be done and why, where the spec was not followed,
and what I am unsure about. Written at the end of the build (2026-09-27).

## 0. The one-paragraph summary

The complete platform exists and is tested: data layer, 13 baselines, three TSFM wrappers,
walk-forward engine, statistics (DM-HLN with HAC, Holm, MCS, pooled tests, contamination
test with placebo, synthetic control, economic illustration), generated report and
dashboard, and an 11-lesson track. **But the build environment could not reach Yahoo
Finance or Hugging Face**, so no real market data were used and no foundation model was
ever run with its real weights. Every committed number is computed on synthetic fixtures,
and all three TSFMs are reported `UNAVAILABLE`. The research question is therefore **not yet
answered**; running `make reproduce` on a normal internet connection is the next step.

## 1. What was built, build by build

| Build | Commit | Contents |
|---|---|---|
| 01 | `2109205` | uv project (Python 3.11, one `uv.lock`), pydantic YAML configs + config hashing, `ForecastOrigin` (the single slicing point) + label-availability mask, future-perturbation leakage detector **with negative controls**, seeding, SHA-256 hashing, Parquet provenance, `PREREGISTRATION.md`, `DECISIONS.md`, `GLOSSARY.md`, lesson infrastructure, lesson 03, Makefile, CI |
| 02 | `255adf0` | `DataProvider` (yfinance, CSV folder, fixtures), immutable raw cache with manifest and integrity checks, cleaning with a full audit trail, targets (percent log returns, Garman–Klass variance, log volume, h-step aggregation), synthetic GARCH/HAR/volume generators with oracle forecasts, committed fixtures, lessons 01–02 |
| 03 | `da0c03e` | `Forecaster` interface, 13 baselines, walk-forward engine (expanding/rolling, re-fit schedules, parallel with per-task seeds), leakage tests for every (baseline, target) pair and for the engine, recovery tests on synthetic data, lesson 04 |
| 04 | `03cc708` | Chronos-Bolt / TimesFM 2.5 / Moirai 1.1 adapters (checked against the real library code with tiny randomly initialised models, tests only), forecast cache keyed by the exact context hash, `UNAVAILABLE` handling, contamination windows (amendment A1), synthetic control, `PRETRAINING-DATA.md`, lesson 05 |
| 05 | `11f0663` | Metrics (MSE, MAE, QLIKE, pinball, CRPS, direction, OOS R²), DM-HLN-HAC (amendment A2), Holm, MCS (T_max/T_R), stationary bootstrap, pooling, contamination Δ test, economic backtest, proxy alignment revised (amendment A3), evaluation orchestrator, lessons 06–08 |
| 06 | `1fc055d` | Pipeline stages and CLI (`run`, `evaluate`, `report`, `all`), `make smoke` / `reproduce` / `reproduce-fixtures`, generated `RESULTS.md` + figures, `default_fixtures` verification run, lesson 09 |
| 07 | `9cbe4fa` | Self-contained static dashboard (`reports/dashboard/index.html`), per-asset differential series, lesson 09 pointer |
| 08 | see §9 | Pinball losses reported separately, `make doctor`, `make flashcards`, lessons 00 and 10, lessons index, README quickstart, `DEFINITION-OF-DONE.md`, this report, provenance "dirty" flag ignores generated outputs, artifacts regenerated from the clean Build 08 tree |

CI (`.github/workflows/ci.yml`: lint, config validation, full pytest suite including
notebook execution, `make smoke`) was green on GitHub Actions for every build commit.

## 2. What was actually run, and how long it took

All timings are from the build container (4 CPU cores, 15 GB RAM, no GPU).

| Run | Data | TSFMs | Wall time |
|---|---|---|---|
| `make smoke` (`configs/smoke.yaml`) | 4 synthetic fixture tickers, test period 2023-01 → 2026-06, stride 10 | UNAVAILABLE (HF blocked) | ≈ 40 s end to end |
| `make reproduce-fixtures` (`configs/default_fixtures.yaml` = default design on 5 fixture tickers) | synthetic, test period 2015-01 → 2026-06, stride 5, both windows, B = 1000 | UNAVAILABLE | ≈ 3 min end to end (baselines 107 s, synthetic control 45 s, statistics ≈ 15 s) |
| `make reproduce` (`configs/default.yaml`) | real Yahoo data | — | **not run**: Yahoo and Hugging Face blocked |
| Test suite (`make test`) | fixtures + simulations | TSFM adapters with random weights | ≈ 2.5 min locally, ≈ 3 min in CI |

Extrapolation (not a measurement): the default baselines on 26 real assets should take about
15 minutes on 4 cores; TSFM inference is unmeasured (Chronos-Bolt tiny should be fast;
TimesFM 200M with flip-invariance doubles its forward passes; Moirai draws 100 samples).

## 3. Models and data sources that were UNAVAILABLE, and why

| Item | Why | What happened instead |
|---|---|---|
| `chronos_bolt_tiny` (amazon/chronos-bolt-tiny) | `huggingface.co` denied by the environment's egress policy (HTTP 403 at the proxy) | Reported `UNAVAILABLE` with the error text in `model_status.json`, every report and the dashboard. Adapter verified against `chronos-forecasting 2.3.2` with a tiny random-weight model (tests only). |
| `timesfm_2p5_200m` (google/timesfm-2.5-200m-pytorch) | same | same; adapter verified against `timesfm 3.0.2` with a randomly initialised 200M model |
| `moirai_1p1_small` (Salesforce/moirai-1.1-R-small) | same | same; adapter verified against `uni2ts 2.0.0` with a tiny random-weight module |
| Yahoo Finance (`query1.finance.yahoo.com`) | denied by egress policy (yfinance then reports a misleading "possibly delisted" error) | All results on committed synthetic fixtures; provider tested with a mocked `yfinance` |
| Stooq, Tiingo, Alpha Vantage, arXiv, OpenReview, PMLR, vendor blogs, HF model cards | denied | `PRETRAINING-DATA.md` tags every claim by how it was verified; many remain unverified |

## 4. Deviations from the spec, and why

1. **No real data, no real TSFM outputs** (network policy): see §3. `make reproduce` was
   verified on fixtures instead (`configs/default_fixtures.yaml`, D-037), as the spec allows.
2. **Checkpoints** (D-005): TimesFM 2.5-200M rather than 1.0-200M (same size; 1.0 needs the
   archived `timesfm==1.3.0` with an incompatible API); Moirai **1.1**-R-small rather than the
   newer 2.0-R-small (both "small"; 1.1's corpus is public and auditable, 2.0 includes
   non-public Salesforce data).
3. **Three amendments to the pre-registration**, all before any real-data or TSFM result:
   A1 effective release date (weights' commit date) for contamination windows; A2 HAC kernel
   for overlapping 20-day targets after a size simulation showed 9–12% false rejections;
   A3 proxy-alignment constant after the smoke fixtures showed one jump day halving it.
   A3 was motivated by *baseline results on synthetic data*; an auditor may reasonably see
   that as a forking path, though the change makes the baselines stronger, not the TSFMs.
4. **Probabilistic evaluation only at h = 1** (D-012): quantiles of an h-step sum cannot be
   recovered from per-step quantiles without a dependence assumption.
5. **CRPS is the nine-decile approximation** (D-012), 5–10% above the exact CRPS for a normal
   forecast in tests; identical treatment for all models.
6. **Moirai sees 532 observations** (512 conditioning + 20 used by its own `patch_size="auto"`
   selection) rather than exactly 512 (D-030).
7. **Universe fixed in Build 01** (in the pre-registration), earlier than the spec's Build 02,
   to commit to it before any code touched data.
8. **Eleven lessons** (00–10) rather than ten; the prose budget is enforced as ≤ 650 words
   (README + notebook markdown) for "about 600".
9. **Dashboard scope** (D-038): per-asset differential series only for the expanding window;
   per-asset DM tests only for the common clean window (file size).
10. **Dependency versions are older than current** (numpy 1.26, pandas 2.1, scipy 1.11,
    torch 2.4) because `uni2ts 2.0.0` pins them and one environment was preferred (D-001);
    `huggingface-hub<1.0` is a precautionary constraint (D-004).
11. **LightGBM via its native API** (no scikit-learn dependency; D-024).

## 5. Known weaknesses, shortcuts and things I am unsure about

**Never executed against the real services (highest risk):**
- `YFinanceProvider.fetch` has only been tested with a mocked `yfinance`. Column names,
  time zones and the exclusive `end` were handled from reading the library source.
- `fetch_weights` (Hugging Face `snapshot_download`) and the weight-commit-date lookup
  (`HfApi.list_repo_tree(..., expand=True)`) never succeeded here. Loading each model from a
  local snapshot directory follows the libraries' code paths, which I read but could not run
  with real files. If a model fails locally, it will be reported UNAVAILABLE with the reason,
  not crash the run.
- TSFM inference time and memory on a laptop are unmeasured.

**Statistics:**
- DM-HLN over-rejects in small samples (≈ 7–13% at nominal 5% for T ≈ 50 in simulation);
  TimesFM 2.5's clean window gives only ≈ 50 origins at stride 5. Results with T < 100 are
  flagged `small_sample`.
- The contamination test has low power (short clean windows) and is confounded by market
  regime; the placebo only partly controls this. Its one-sided p-value is a percentile-
  bootstrap p-value and the two windows are resampled independently, both approximations.
- Block length `max(⌈T^{1/3}⌉, 2(q_h+1))` is a rule of thumb, not data-driven.
- Holm families are defined by (period, window); a different grouping would change which
  secondary results "survive". The primary family (27) is as pre-registered.
- Per-asset families are large (Holm over hundreds of tests in the default run), so they are
  conservative by design.

**Models and data:**
- HAR is the levels specification by OLS with a floor; LightGBM hyper-parameters are fixed
  and untuned; re-fit schedules (GARCH monthly, LightGBM yearly) are a cost compromise.
- GARCH/EWMA need a scaling to the open-to-close GK target (amendment A3); any such
  calibration is a modelling choice.
- The Garman–Klass target excludes overnight moves for every model, and is biased low by
  discrete trading (≈ 9% at 390 steps in the simulator).
- The fixtures approximate the NYSE calendar with US federal holidays and make log volume
  independent of volatility; the seasonal-naive model maps weekdays with business-day offsets.
- The stock universe is survivorship-biased (D-003).
- Cleaning flags but does not alter suspect splits; a genuinely unadjusted split in Yahoo data
  would pass through (flagged).

**Reproducibility and provenance:**
- Results are reproducible to floating-point tolerance, not bit-for-bit, across machines
  (BLAS threads, summation order; D-025). Moirai's sampled forecasts depend on batch
  composition when the cache is partially filled (D-032).
- Artifacts committed before Build 08 recorded the parent commit with `dirty: true`. The
  final artifacts are regenerated from the clean Build 08 tree (see §9).
- `results/default_fixtures/stats/losses.parquet` (15 MB, re-derivable) is not committed;
  its hash is still listed in that report.

**Pretraining-data facts:** several entries in `PRETRAINING-DATA.md` are search snippets or
recollections of papers, clearly tagged. Before writing up, read the papers and model cards.

**Learning layer:** lessons run on synthetic data (so they work offline), lesson 05 shows a
real model only when weights are available, and the word budget is checked automatically but
readability is not.

## 6. What the committed synthetic results show (sanity, not findings)

On the fixtures, the pipeline recovers the data-generating processes: GARCH-family models win
on GARCH-generated series and HAR on HAR-generated ones; the oracle has the lowest loss
against the latent variance; seasonal naive is clearly worst for volume; LightGBM is the
weakest return model. Most secondary comparisons that look significant before correction do
not survive Holm. See `reports/RESULTS.md` (this points at the `default_fixtures` run).

## 7. Exact commands to run next (on your machine)

```bash
# once
uv python install 3.11
make install-all                                   # core + TSFM packages + JupyterLab (~6 GB)
make doctor                                        # fix anything marked ✗
make doctor ONLINE=1                               # pre-downloads the three model checkpoints

# the real study
make fetch-data CONFIG=configs/default.yaml        # Yahoo -> data/raw (hashed, immutable)
make smoke                                         # now also runs the 2-ETF real subset
make reproduce                                     # full pre-registered study
open reports/RESULTS.md reports/dashboard/index.html

# learning
uv run jupyter lab                                 # start with lessons/00-orientation
make flashcards                                    # flashcards.csv for Anki
```

If `make fetch-data` fails for every ticker, Yahoo is blocking you: wait, or download
Yahoo-format CSVs by hand and use `provider: csv` (D-022). If a model shows as UNAVAILABLE,
the reason is in `results/default/model_status.json`.

**Before believing any real result, check:** the TSFM rows in `model_status.json` say
AVAILABLE with a resolved revision; `weights_commit_date` does not move the clean windows
much; the primary table has T ≥ 100 where you draw conclusions; and the placebo Δs in the
contamination section.

## 8. File map for the auditor

Leakage: `src/tsfm_rc/origin.py`, `leakage.py`, `tests/test_leakage_harness.py`,
`tests/test_baselines_leakage.py`, `tests/test_engine.py`, `tests/test_tsfm.py`.
Statistics vs references: `tests/test_stats.py` (statsmodels HAC, `dieboldmariano`,
statsmodels Holm, `arch` MCS, CRPS closed form, Monte Carlo size).
Traceability: `tests/test_reports.py`, `tests/test_dashboard.py`, `src/tsfm_rc/provenance.py`.
Design history: `docs/PREREGISTRATION.md` §11, `docs/DECISIONS.md`.

## 9. Build 08 commit and regenerated artifacts

*(filled in by the commit that follows Build 08)*
