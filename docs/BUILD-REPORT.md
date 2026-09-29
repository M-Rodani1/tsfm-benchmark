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

**Audit-01 (§10)** added:
- *Amendment A4:* stride-1 primary tests in the clean windows, with a Kiefer–Vogelsang
  fixed-b test chosen by simulation.
- *The website* (`site/`): all 11 lessons run in the browser, results are published with
  provenance, plus review, notes and synced progress. Every lesson is verified in real
  Pyodide by CI.
- *Small statistical corrections.*
- *A fix that makes the committed artifacts reproducible bit for bit* on x86-64 machines.

**Guided journey (§11)** added a route through the whole project to the site:
- a first-visit tour;
- one "Do this next" card;
- a "Your path" roadmap;
- a page per terminal step, with checks of pasted terminal output.

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
| 08 | `158d885` (+ artifacts commit, §9) | Pinball losses reported separately, `make doctor`, `make flashcards`, lessons 00 and 10, lessons index, README quickstart, `DEFINITION-OF-DONE.md`, this report, provenance "dirty" flag ignores generated outputs, artifacts regenerated from the clean Build 08 tree |

CI (`.github/workflows/ci.yml`: lint, config validation, full pytest suite including
notebook execution, `make smoke`) was green on GitHub Actions for every build commit.

## 2. What was actually run, and how long it took

All timings are from the build container (4 CPU cores, 15 GB RAM, no GPU).

| Run | Data | TSFMs | Wall time |
|---|---|---|---|
| `make smoke` (`configs/smoke.yaml`) | 4 synthetic fixture tickers, test period 2023-01 → 2026-06, stride 10 | UNAVAILABLE (HF blocked) | ≈ 40 s end to end |
| `make reproduce-fixtures` (`configs/default_fixtures.yaml` = default design on 5 fixture tickers) | synthetic, test period 2015-01 → 2026-06, stride 5, both windows, B = 1000 | UNAVAILABLE | ≈ 3 min end to end (baselines 107 s, synthetic control 45 s, statistics ≈ 15 s) |
| `make reproduce` (`configs/default.yaml`) | real Yahoo data | — | **not run**: Yahoo and Hugging Face blocked |
| Test suite (`make test`) | fixtures + simulations | TSFM adapters with random weights | 302 tests: ≈ 4.3 min locally (with the TSFM extra), ≈ 3 min in CI (4 tests needing the TSFM extra skipped) |
| Site tests (`site/`, Audit-01) | fixtures, published synthetic results | — | 45 Vitest tests (seconds); 20 Playwright tests, ≈ 1 min in CI including all 11 lessons in real Pyodide |

**Amendment A4 (Audit-01) cost.** The primary family now uses stride-1 origins in the clean
windows (a separate *primary pass*; see §10).
- *Baselines:* one extra pass with 2 models per (asset, target), expanding window only, over
  ≈ 541 origins (from 2024-07-30). On the fixtures it adds ≈ 15 s to `make smoke` and about a
  minute to `make reproduce-fixtures`.
- *TSFMs:* only the in-window origins that are not on the stride-5 grid are new (the output
  cache serves the rest). On the default calendar:

  | model | stride-1 clean origins | new origins | new requests | vs its stride-5 requests (45,864) |
  |---|---|---|---|---|
  | Chronos-Bolt | ≈ 439 | 352 | 27,456 | +60% |
  | TimesFM 2.5 | ≈ 238 | 191 | 14,898 | +32% |
  | Moirai 1.1 | ≈ 541 | 433 | 33,774 | +74% |

  Counts use an approximate holiday calendar.

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
- Results are reproducible bit for bit on x86-64 machines with the locked wheels, because
  `tsfm-rc` pins OpenBLAS's generic kernels (D-054, Audit-01). Elsewhere (e.g. ARM) they
  agree to optimiser tolerance: GARCH-family forecasts on the fixtures moved by up to 0.036
  between CPU kernels (D-054). Moirai's sampled forecasts depend on batch
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
A4: `tests/test_a4_primary.py`, `src/tsfm_rc/eval/fixedb.py`, `src/tsfm_rc/eval/size_study.py`.
Website: `site/README.md`; security and data safety `site/tests/rls.test.ts`,
`site/tests/sync.test.ts`, `site/tests/db.test.ts`, `site/tests/scripts.test.ts`,
`netlify.toml`; browser `site/e2e/`.
Design history: `docs/PREREGISTRATION.md` §11, `docs/DECISIONS.md`.

## 9. Build 08 commit and regenerated artifacts

- **Build 08 commit:** `158d88556de1ddb5ef7b01d8b5e22b97cf4f69e3`. GitHub Actions CI run
  `36353141857` on that commit: success (lint, config validation, 253 tests, `make smoke`).
- **Regenerated artifacts:** from a clean checkout of that commit, `make reproduce-fixtures`
  (2 min 57 s) and then `make smoke` (37 s) were run. Every `provenance.json`, every
  Parquet provenance record and both `RESULTS.md` provenance sections now show commit
  `158d885…` with `working tree dirty: False`. (`git_info()` treats `results/` and `reports/`
  as outputs, so rewriting them does not count as dirty.)
- **What changed in the numbers:** nothing. Every stored table was compared cell by cell
  (`pandas.testing.assert_frame_equal`, exact) with the version committed in Build 08.
  All are identical except `results/default_fixtures/stats/probabilistic.parquet`. That table
  was produced before Build 08, so it gains the three pinball columns; its other columns are
  identical. Only the artifact SHA-256 values change, because the embedded provenance changed.
- The follow-up commit ("Build 08 (artifacts)") contains only these regenerated
  `results/` and `reports/` files and this section.

## 10. Audit-01 corrections

Written 2026-09-28, after the Audit-01 correction prompt. Each fix was committed separately
to `main`, by the repository owner's account, after the full local test suite passed. CI was
red on two intermediate fix-2 commits (`a0b35fa`, `e9f517e`), and the next commits fixed
what it found (§10.4). CI is green from `b24357e` on.

### 10.1 Commits

| Fix | Commit | What |
|---|---|---|
| 1 | `3a32639` | Amendment A4: stride-1 primary tests in the clean windows, size study, KV fixed-b test, separate primary pass, artifacts regenerated |
| 2 (part 1) | `0fd6790` | Lessons moved to `site/content/` (single source; notebooks generated), `make publish-results`, browser-safe `tsfm_rc` (NumPy GARCH, `learn.stats_table`) |
| 2 (part 2) | `a0b35fa` | The website `site/`, Supabase schema with RLS, `netlify.toml`, `docs/DEPLOY.md`, Vitest + Playwright, CI job `site` |
| 2 (part 3) | `e9f517e` | Robust NumPy GARCH optimiser (CI found a 0.09 log-likelihood shortfall against `arch`); e2e waits for the lesson to render |
| 2 (part 4) | `b24357e` | No lost writes when the page reloads right after an action (found by CI); lesson browser tests isolated and diagnosable |
| 3 | `89b2306` | `dropped_nonfinite=N` flag, oracle-ratio bootstrap CIs and honest wording, PRETRAINING-DATA checklist, OpenBLAS kernel pinned (D-054) |
| 3 (artifacts) | `e930b87` | `results/`, `reports/` and `site/public/data/results/` regenerated from the clean fix-3 tree |
| finish | the commit adding this section | DEFINITION-OF-DONE (site criteria and A4), this section, browser notes on lessons 00 and 10 |

### 10.2 Fix 1: amendment A4 and its simulation

*What changed.* The 27 primary tests and the clean side of the contamination test now use
every trading day inside each TSFM's clean window (stride 1). Everything else keeps stride 5,
and the stride-1 forecasts are a separate pass with separate artifacts (D-041), so no
secondary number moved. `tests/test_a4_primary.py` proves the latter cell by cell against
the Build 08 artifacts. The same `h_eff`/lag rule now drives `dm_primary`, the contamination
test and the `ratio_ci` block lengths (`h_eff = ceil(h / stride)`).

*Simulation* (`src/tsfm_rc/eval/size_study.py`, 5,000 replications per cell, seed
20260928; full 36-cell table in D-039). Grid: T ∈ {100, 250, 450}, h ∈ {1, 5, 20}, four
null processes (AR(1) with φ = 0, 0.3, 0.6, and a GARCH squared-error differential).

| test at stride 1 | worst-case \|size − 5%\| | mean \|size − 5%\| | size range |
|---|---|---|---|
| **Kiefer–Vogelsang fixed-b (Bartlett, bandwidth T), pre-registered** | **0.072** | **0.014** | 0.036–0.122 |
| Bartlett, lag max(h − 1, NW) + fixed-b critical values | 0.109 | 0.050 | 0.045–0.159 |
| Bartlett, lag max(h − 1, NW), HLN | 0.118 | 0.055 | 0.050–0.168 |
| rectangular, lag h − 1, HLN (R's `dm.test`) | 0.281 | 0.053 | 0.046–0.331 |

The KV variance is a sum of squares, so it cannot be negative. It is zero only for a
constant series, and the test is then reported as p = NaN with the flag `zero_variance`,
never replaced by another rule. The chosen test still over-rejects at T = 100, h = 20 (up
to 12.2%). Every primary row therefore carries `sim_size_max`, the worst simulated size at
the nearest simulated T not above its own. It costs power: at a mean shift where an ideal
test has 80% power, it rejects 60–72% (D-039).

*Inference cost* of the extra stride-1 origins: §2 (Chronos-Bolt +60%, TimesFM +32%,
Moirai +74% forecast requests; baselines about +1 minute on the fixtures).

### 10.3 Fix 2: the website

A static Vite + React + TypeScript app in `site/`, built by Netlify. Its pages:
- Home (continue where you stopped, due cards, the pending terminal task);
- Lessons and the lesson pages;
- Results;
- Review;
- Notes & log;
- Research status (generated from this file and PREREGISTRATION.md);
- Progress & sync.

Python runs in the browser: Pyodide 314.0.7 in a Web Worker, with the core self-hosted and
the packages loaded from the pinned CDN path. `tsfm_rc` is installed from a pure-Python wheel
built from `src/`. Progress is stored in IndexedDB first and synced to Supabase when
configured (D-043 to D-051).

**Where an exercise does not run the study's own code** (each says so on its page):

| Lesson | What runs in the browser instead | Evidence it is the same |
|---|---|---|
| 04 AR, GARCH, HAR | `tsfm_rc.models.garch_np`, a NumPy/SciPy re-implementation of the `arch` GARCH(1,1)-t estimator (`arch` does not run in Pyodide) | `tests/test_garch_np.py`: same variance path and likelihood as `arch` to 1e-10 at fixed parameters; the fitted likelihood is at least as high as `arch`'s (within 0.01) on every fixture, with the same parameters |
| 00, 09, 10 | **Precomputed**: stored results read from the published JSON (`make publish-results`) instead of the Parquet files (no `pyarrow` in the lesson sandbox) | `tests/test_publish.py`: the JSON round-trips to the Parquet tables exactly (every float) |
| 05 foundation models | Nothing: the models need PyTorch and their weights. The loading cell prints why, and the lesson points to the Results page | — |
| 02 volatility | The Garman–Klass discretisation simulation uses 20,000 paths (the study's function defaults to 200,000) | Same function; only `n_paths` differs |

All other lessons (01, 03, 06, 07, 08) run the study's own code unchanged.

### 10.4 What was verified in a browser, and where

- **CI only** (GitHub Actions, job `site`, Chromium with real Pyodide, `REQUIRE_PYODIDE=1`
  so the tests cannot be skipped):
  - every lesson: all code cells run, the unsolved starter fails the checker with an
    explanation, the solution passes;
  - one exercise failing and then passing, with tiered hints.

  The build container cannot reach the Pyodide package CDN (egress policy), so these tests
  are skipped there.
- **In CI and in the build container** (Playwright, production build, production security
  headers):
  - completing a step, then reloading;
  - autosave surviving a closed tab;
  - export then import;
  - reviewing due cards, then reloading;
  - the Results page with provenance and the SYNTHETIC label;
  - prerequisite override;
  - offline use after a first visit.
- **Also in CI:** every lesson under Pyodide's exact package versions on CPython 3.14.
- **In the build container only:** a manual check that the self-hosted Pyodide core starts
  under the production Content-Security-Policy.
- **Two defects were found only by the CI browser run and fixed:**
  - progress written right before a reload could be lost (`b24357e`, now covered by a unit
    test);
  - a prerequisite-lock timing issue in the tests (`e9f517e`).

The first fully green browser run was GitHub Actions run `36492069235` on `b24357e`: all 20
Playwright tests passed, including all 11 lessons in real Pyodide, in 57 s. The run on
`e9f517e` had timed out on lesson 00 before the part-4 changes. Its trace could not be
downloaded here (the artifact host is blocked), so it is not known which of those changes
cured it. Clicks now fail after 60 s with Playwright's reason, and the test prints
diagnostics, so a recurrence would explain itself in the CI log.

### 10.5 Fix 3: small corrections

- `dm_test` appends `dropped_nonfinite=N` to its flag when it drops NaN/inf values
  (`tests/test_stats.py::test_dm_reports_dropped_nonfinite_values`). No stored flag changed:
  the study's own series have no gaps.
- **Synthetic control.**
  - Each oracle ratio has a 95% stationary-bootstrap CI.
  - The report and summary call a ratio below 1 whose CI covers 1 sampling noise.
  - The figure draws the CIs.
  - Tested in `tests/test_evaluate.py::test_synthetic_oracle_ratio_has_bootstrap_ci_and_honest_wording`.
- **PRETRAINING-DATA.md** opens with a checklist of every claim not verified from a primary
  source (C1–C5, T1–T6, M1–M3, R1–R2). A test requires every `[S]`, `[M]` and `[UNVERIFIED]`
  row to be on it.

### 10.6 A reproducibility finding (D-054)

Regenerating the artifacts for fix 3 on a new build host moved GARCH forecasts, even though
no forecasting code had changed. The cause is the OpenBLAS libraries bundled with the
NumPy/SciPy wheels, which pick a CPU-specific kernel.

**Scale** (smoke run):
- forecasts moved by up to 0.036;
- DM p-values moved by up to 0.011, with no 5% decision changed;
- one MCS p-value of two near-tied GARCH variants moved from 0.255 to 1.000.

**Fix.** Every committed artifact is reproduced exactly with OpenBLAS's generic Prescott
kernels. `tsfm-rc` now pins them on x86-64 and records the choice in provenance.

**Numbers after regeneration.** The regeneration ran `tsfm-rc all` on default_fixtures
(3 min 51 s) and then smoke (57 s), both from a clean checkout of `89b2306`. It was slower
than in Build 08 (2 min 57 s and 37 s) because the generic kernels are slower. Every table committed in fix 1 is identical cell by cell
(`pandas.testing.assert_frame_equal`, exact), and so are all forecast files. The one
difference is the synthetic-control table, which gains the three CI columns. Artifact
hashes change because provenance changed (commit, the kernel field).

### 10.7 Known weaknesses after Audit-01

- **Browser tests run only in CI.** The build container cannot reach the Pyodide package CDN
  (egress policy), so the real-Pyodide lesson tests have only ever run on GitHub Actions.
- **Packages come from a CDN.** The site loads Pyodide's packages from jsDelivr on the first
  visit. If the CDN is blocked, lessons show a clear "Python could not start" message.
  Self-hosting the packages would add about 40 MB to every deploy.
- **Parts of the site never run for real.** Supabase login and sync, the Netlify deploy and
  the DNS change have not been done: they need the owner's accounts. RLS, the sync rule
  and the trigger are tested on a real Postgres engine (PGlite), not on Supabase itself.
- **Conflict handling is simple.** Last-write-wins per record keeps the later of two
  offline edits to the same note; clock skew between devices can reorder near-simultaneous
  edits (D-047).
- **Statistics.**
  - The A4 test buys accurate size with power: 60–72% where an ideal test has 80% (D-039).
  - At T ≈ 100 with 20-day targets it still over-rejects (≈ 12%).
- **Reproducibility across hardware.**
  - Bit-for-bit only on x86-64 with the locked wheels.
  - On other hardware, GARCH-family results agree to the tolerance stated in D-054.
- Everything in §5 still applies. Above all, **no result on real data or with real
  foundation-model weights exists yet.**

### 10.8 Manual go-live steps

`docs/DEPLOY.md` has the click-by-click version. In short:

1. **Supabase.**
   - Create a project.
   - Copy the Project URL and the public **anon/publishable** key. Never copy the
     service-role key.
   - In the SQL Editor, run `site/supabase/migrations/20260928120000_progress_schema.sql`.
     This creates seven tables, RLS and four `own_rows_*` policies per table.
   - Under Authentication → URL Configuration, set the Site URL and the redirect URLs.
2. **Netlify.**
   - Import `M-Rodani1/tsfm-benchmark`, branch **`main`**. `netlify.toml` sets base `site`,
     the command `npm run build` and the publish directory `dist`.
   - Under Site configuration → Environment variables, add these, then deploy:

     | Variable | Value |
     |---|---|
     | `VITE_SUPABASE_URL` | the Project URL |
     | `VITE_SUPABASE_ANON_KEY` | the anon/publishable key |
     | `VITE_ALLOWED_EMAIL` | your email address (optional) |
3. **First sign-in.**
   - Open the site and request a magic link under Progress & sync.
   - Sign in.
   - Then disable **Allow new users to sign up** in Supabase.
4. **DNS.**
   - In Netlify, add the custom subdomain.
   - At your DNS provider, create `CNAME <subdomain> → <site>.netlify.app` and no A record.
   - Once DNS verifies, provision the certificate.
   - Set the same address as the Supabase Site URL.
5. **Done.** `main` is the default branch on GitHub; the owner changed it after Audit-01.
6. **After the real study.** Run `make reproduce`, then `make publish-results`, then commit
   and push `site/public/data/results`. Netlify rebuilds, and phases 1, 2 and 5 of *Your
   path* complete by themselves (§11).

## 11. Guided journey (site fix)

Written 2026-09-29, after the "Guided journey" prompt. The problem: the site had lessons, a
Home "continue" card and a terminal-task card, but a first-time visitor could not tell the
overall route, the order, how terminal work fits alongside the lessons, or what "done" means.

### 11.1 Commits

| Part | Commit | What |
|---|---|---|
| 1/4 | `5dcaee4` | `journey.yaml` and the four terminal tasks, build-time validation, `journey.ts` (statuses, `nextAction()`), pasted-output checks tested on real captured output, table `journey_state` with RLS, doctor fix catalog |
| 2/4 | `23a64cb` | Tour, Home "Do this next", "Your path", terminal task pages, breadcrumbs, one "Next step" button, SYNTHETIC banners, browser tests |
| 3/4 | `51ba7d0` | Lesson 00 "How to use this site", migration upgrade tests, `site/README.md`, `docs/DEPLOY.md`, DECISIONS D-055 to D-058 |
| 4/4 | the commit adding this section | DEFINITION-OF-DONE rows 17–21, this section |

### 11.2 The route

Eight phases, defined in `site/content/journey.yaml`:

| Phase | Where | Steps |
|---|---|---|
| P0 Start here | browser | tour, lesson 00 |
| P1 Set up your laptop | laptop | clone, uv, Python 3.11, `make install-all`, `make doctor ONLINE=1` |
| P2 Launch the real study | laptop | `make fetch-data`, `make reproduce` ("Start this now and keep learning while it runs.") |
| P3 Foundations | browser | lessons 01–04 |
| P4 Models and statistics | browser | lessons 05–08 (optional: review flashcards) |
| P5 Publish the real results | laptop | `make publish-results`, commit, push |
| P6 Read your results | browser | lesson 09, the Results page |
| P7 Write it up | browser + laptop | lesson 10, `make test` and send for audit |

After lesson 00 the site recommends P1 and P2 at once. P3–P4 run in parallel with P2, and
P6–P7 need real results. Lessons are never hard-locked.

### 11.3 How each terminal step is detected as done

| Step | Automatic | From pasted output (success) | Otherwise |
|---|---|---|---|
| P1 set up | a real `default` run is published | `make doctor ONLINE=1`: ran to the end, no ✗, no ! except real-data cache, results, lessons or uv | “I've done this” (shown as self-reported) |
| P2 run the study | same | `make reproduce`: `[evaluate]`, `[report] …/reports/default/…`, `[dashboard]`; another config is rejected by name; UNAVAILABLE models are flagged | same; a start button (or output showing the run started) marks it running |
| P5 publish | same (the only completion) | `make publish-results` with a `(real data)` `default` run: progress only, “now commit and push” | same |
| P7 audit | — | `make test`: the summary line, some tests passed and none failed | same |

Real results means a published non-synthetic run named `default`. `publish.py` labels every
run synthetic unless its data came from Yahoo Finance or CSV (D-055).

### 11.4 What was verified, and how

- **Unit tests** (`site/tests/`, 79 in all; 45 before this fix):
  - `nextAction()` and the statuses in eight situations, from a fresh user to all done;
  - breadcrumbs;
  - YAML validation, including the bug below;
  - the output checks on real captured output;
  - RLS for `journey_state`: policies and grants equal the other tables', a re-run of the
    migration, and the upgrade from the pre-journey schema.
- **Browser tests** (`site/e2e/journey.spec.ts`, 4 tests, in CI and locally): the tour to
  lesson 00; finishing lesson 00 making Phase 1 next; a real failed doctor output rejected
  with its fixes and a real success output completing Phase 1; reloads keep everything; the
  study running; self-report and reset; OS tabs; SYNTHETIC banners.
  - The 8 existing app flows were updated to the new Home with the same assertions.
  - The 12 real-Pyodide lesson tests still pass in CI with the new lesson page.
- **Python:** `tests/test_doctor_flashcards.py` keeps the doctor's fix catalog in sync and
  fails if the CLI's wording drifts from the site's parser. 304 tests pass.
- **Captured output** (`site/tests/fixtures/cli/`): every file is real output of the command
  named in its README, run on 2026-09-29, with two exceptions:
  - the Phase 1 success case ran the real doctor against a staged model-weights cache,
    because Hugging Face is blocked here;
  - the tests derive the real study and a real publish from real captures by changing only
    the run name or label.
- **A manual browser pass** with screenshots found one defect the tests had missed: an
  unquoted YAML item (`Windows: …`) became a mapping and crashed the Phase 1 page. It was
  fixed, and the validator now rejects non-string text (a test covers it).

### 11.5 Known weaknesses

- **The laptop instructions have not been followed end to end on a real laptop.**
  - *Run for real here:* `df`, `make doctor` (both modes), `make fetch-data`,
    `make reproduce`, `make reproduce-fixtures`, `make publish-results`, `make test` and
    `uv python install 3.11` ran in the build container (Linux).
  - *Written from the tools' documentation, not run:* the macOS and Windows commands
    (`xcode-select`, Homebrew, `wsl --install`, `powercfg`, `caffeinate`), `gh` for a private
    repository, `systemd-inhibit` and the uv installer.
- **The real study's duration is unmeasured.** "Several hours" is an estimate (§2).
- **The site cannot see the laptop.** "Study running" is the learner's own click (or pasted
  output showing it started). Phases 2 and 5 complete automatically only after a push has
  made Netlify rebuild.
- **Self-reported steps carry no evidence.** They are labelled as self-reported everywhere
  and can be reset.
- **Brief deviation: a sixth status.** The brief lists five statuses. *upcoming* was added
  because calling an available step "locked" would be false (D-055).
- **Conflict handling.** Journey state has the same last-write-wins limitations as the rest
  of the progress (D-047).

### 11.6 A defect found after release, and its fix

The owner reported a blank page after the journey went live. Every browser that had used the
site before could not start: its local database was opened with a hard-coded version 1, so
the new `journey_state` store was never created. Fresh browsers were fine, which is why every
test passed: they all start from an empty browser.

**The fix** (D-057):
- the database now upgrades itself whenever a store is missing, keeping all data;
- a tab still running the old site produces a "close the other tabs" message instead of
  hanging;
- any failure while starting shows a message instead of a blank page.

**The lesson for the tests.** Tests now include a browser that already has the old
database, and they must keep doing so for every future schema change. The new tests fail
on the released code and pass with the fix.

### 11.7 What you need to do

- **If Supabase is already set up**, run
  `site/supabase/migrations/20260928120000_progress_schema.sql` again in the SQL Editor. It
  adds `journey_state` with the same protection and keeps your data (tested).
- Otherwise nothing: Netlify rebuilds from `main` on the next push. A browser that showed
  the blank page recovers by itself on the next load, with its progress intact.

