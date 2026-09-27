# Pre-registration: TSFM Reality Check

**Registered:** 2026-09-27, in commit `Build 01` of this repository, **before any model was
evaluated on any data** (real or synthetic). The git history is the timestamp: this file
exists in the Build 01 commit, and forecasting code first appears in Build 03.

**Amendment policy.** Nothing in sections 1–9 may be changed silently. Any change is
appended to section 11 as a dated amendment stating what changed, why, and whether any
result had been seen at the time of the change. Results produced under a superseded
version of the design remain in the report, labelled as such, if they were ever computed.

---

## 1. Research question

Do pretrained time-series foundation models (TSFMs), used **zero-shot**, produce better
out-of-sample forecasts of daily financial **returns**, **realised volatility** and
**trading volume** than strong, cheap classical baselines, under strict walk-forward
evaluation, proper significance testing, and a control for pretraining-data contamination?

A null or negative result is a valid, expected outcome. The design below is fixed so that
no pipeline, metric or sample choice can be tuned after seeing results.

## 2. Data

- **Source:** Yahoo Finance daily OHLCV through the `yfinance` package, behind the
  `DataProvider` interface. Raw downloads are cached immutably with SHA-256 hashes.
- **Period:** 2000-01-03 to 2026-09-25 (fixed end date so the study does not drift).
- **Universe (26 assets, fixed now):**
  - ETFs (5): SPY, QQQ, IWM, TLT, GLD.
  - Stocks (21, two per GICS sector where possible, all listed before 2000):
    AAPL, MSFT (Info Tech); JNJ, PFE, UNH (Health Care); JPM, BAC (Financials);
    PG, KO, WMT (Staples); HD, MCD, AMZN (Discretionary); XOM, CVX (Energy);
    CAT, UNP (Industrials); VZ, DIS (Communication); NEE (Utilities); SHW (Materials).
  - GLD starts 2004-11-18, so its first origin comes later (it needs `min_train_obs`
    observations). No asset is dropped or added after this date.
  - **Survivorship bias:** the stocks are companies that exist and are large in 2026.
    This conditions on survival (see section 10, Limitations).
- **Prices:** returns use the dividend- and split-adjusted close. The range-based
  volatility uses same-day ratios (H/L, C/O), which are invariant to a multiplicative
  adjustment factor. Volume is split-adjusted as delivered by the provider.
- **Cleaning** (every action is logged to a cleaning report): drop duplicate dates
  (keep last), drop rows with non-positive prices, drop stale rows (zero volume AND
  H = L = O = C), repair OHLC ordering violations by setting H = max(O,H,L,C) and
  L = min(O,H,L,C), set zero volume on a trading row to missing, flag (not alter)
  |daily log return| > 0.35 as a suspect split, record days missing relative to the
  union trading calendar. No winsorising, no outlier removal.
- **Synthetic fixtures** (committed; used for tests, smoke runs and the synthetic control)
  are generated from known GARCH / HAR processes by `tsfm_rc.data.synthetic` with a
  fixed seed.

## 3. Targets and horizons

Let `C_t`, `O_t`, `H_t`, `L_t`, `V_t` be adjusted close, open, high, low, volume on
trading day `t` (the asset's own trading days). Horizons: **h ∈ {1, 5, 20}** trading days.

- **Returns.** Daily log return in percent `r_t = 100 · ln(C_t / C_{t-1})`.
  Target: cumulative return `y^ret_{t,h} = Σ_{i=1..h} r_{t+i}`.
- **Realised volatility.** Daily Garman–Klass (1980) variance, in %²:
  `σ²_t = 100² · [ 0.5 · ln(H_t/L_t)² − (2 ln 2 − 1) · ln(C_t/O_t)² ]`.
  Target: mean daily variance over the horizon `y^rv_{t,h} = (1/h) Σ_{i=1..h} σ²_{t+i}`.
  (Justification: `docs/DECISIONS.md`, D-006. It measures open-to-close variance and
  excludes the overnight gap; this is the same for every model.)
- **Volume.** Target: mean log volume `y^vol_{t,h} = (1/h) Σ_{i=1..h} ln V_{t+i}`.
- A target window containing a missing input (e.g. zero volume set to missing, or
  H = L) makes that target missing; such cases are counted and reported, never imputed.

## 4. Forecast origins and windows

- **Origins:** every **5th** trading day (stride 5) on the union trading calendar,
  starting at the first trading day on/after **2015-01-02**, provided the asset has at
  least **1000** observations up to and including the origin.
- **Information set:** a forecast at origin `t` uses only rows with timestamp ≤ `t`
  (enforced by `ForecastOrigin`, tested by future-perturbation tests).
- **Primary window:** **expanding** (all data from 2000 up to `t`).
  **Robustness:** rolling window of the last 1000 trading days (baselines only; TSFMs
  always see a fixed context).
- **Direct regressions** only use training pairs whose label window has ended by `t`.
- **Re-fit schedule** (in origins): GARCH and GJR-GARCH every 4 origins (≈ monthly);
  LightGBM every 50 origins (≈ yearly); every other baseline at every origin. Between
  re-fits, parameters are frozen but all state (filters, features, lags) is updated with
  data up to `t`.

## 5. Models

### 5.1 Baselines (hyper-parameters fixed in advance, no tuning on test data)

| Target | Model | Specification |
|---|---|---|
| returns | `zero` | ŷ = 0 (random walk in log price) |
| returns | `hist_mean` | h × mean of all past daily returns in the window |
| returns | `ar_bic` | AR(p) on daily returns, p ∈ {0..10} by BIC on the training window, iterated to h, summed |
| returns | `lgbm` | LightGBM direct model per h (features in 5.3) |
| rv | `ewma` | RiskMetrics EWMA of squared returns, λ = 0.94, flat forecast |
| rv | `garch` | GARCH(1,1), constant mean, Student-t errors (`arch`), analytic h-step variance |
| rv | `gjr_garch` | GJR-GARCH(1,1,1), otherwise as `garch` |
| rv | `har` | HAR-RV (Corsi 2009) on daily GK variance: OLS of `y^rv_{s,h}` on daily, 5-day and 22-day mean GK variance; direct per h |
| rv | `lgbm` | LightGBM direct model per h |
| volume | `seasonal_naive` | ln V of the most recent same weekday, per step, averaged over h |
| volume | `ar_bic` | AR(p) on log volume, p by BIC, iterated, averaged over h |
| volume | `har` | HAR-style OLS of `y^vol_{s,h}` on 1-, 5-, 22-day mean log volume; direct per h |
| volume | `lgbm` | LightGBM direct model per h |

Return-based volatility models (`ewma`, `garch`, `gjr_garch`) forecast close-to-close
variance, whereas the target is open-to-close GK variance. Their forecasts are multiplied
by `c = mean(σ²_GK) / mean(r²)` computed on the **training window only** (proxy
alignment, D-007). HAR forecasts are floored at 1% of the training-window mean
variance to stay positive.

LightGBM (fixed): 200 trees, learning rate 0.05, 15 leaves, min 50 samples per leaf,
subsample 0.8, column subsample 0.8, L2 = 1.0, single thread, fixed seed.

### 5.2 Foundation models (zero-shot, no fine-tuning)

| Name | Checkpoint | Released | Output used |
|---|---|---|---|
| `chronos_bolt_tiny` | `amazon/chronos-bolt-tiny` (9M) | 2024-11-26 | 9 quantiles (0.1–0.9); point = median |
| `timesfm_2p5_200m` | `google/timesfm-2.5-200m-pytorch` (200M) | 2025-09-15 | 9 quantiles; point = median |
| `moirai_1p1_small` | `Salesforce/moirai-1.1-R-small` (~14M) | 2024-06 (use 2024-06-30) | 100 sample paths → 9 quantiles; point = median |

- **Context length: 512 trading days** (the most recent 512 observations up to `t`),
  identical for all TSFMs. One forecast of 20 steps is made per (series, origin); the
  h ∈ {1,5,20} forecasts are derived from its first h steps.
- **Inputs and aggregation per target** (same rule for all TSFMs):
  - returns: input daily `r_t`; `ŷ_{t,h}` = sum of the per-step medians.
  - rv: input `ln σ²_t` (log GK variance). Per step, the variance forecast is the
    lognormal mean `exp(m + s²/2)` with `m` = median and `s = (q0.9 − q0.1) / 2.5631`
    from the model's own quantiles; `ŷ_{t,h}` = mean of the per-step values.
  - volume: input `ln V_t`; `ŷ_{t,h}` = mean of the per-step medians.
- Missing values in the context (rare) are carried forward from the last valid value.
- Checkpoints are loaded from Hugging Face at `revision: main`; the resolved commit hash
  is stored with every cached forecast. If a checkpoint cannot be downloaded or the
  package cannot be imported, the model is reported as **UNAVAILABLE** everywhere.

### 5.3 LightGBM features (all computed from data ≤ t)

Lags 1–5 of the daily target series; its 5- and 22-day means; lagged daily return,
|return|, ln σ²_GK (1-, 5-, 22-day means) and ln V (1-, 5-, 22-day means); day of week.

## 6. Metrics

- Point: **MSE**, **MAE** for all targets. **QLIKE** for rv:
  `QLIKE(ŷ, y) = y/ŷ − ln(y/ŷ) − 1` (Patton 2011).
  **Directional accuracy** for returns (share of `sign(ŷ) = sign(y)`; undefined for `zero`).
  **Out-of-sample R²** `1 − Σ(y−ŷ)² / Σ(y−ŷ_bench)²` with benchmarks: returns →
  `hist_mean` (Campbell–Thompson 2008), rv → `ewma`, volume → `seasonal_naive`.
- Probabilistic (h = 1 only, where per-step quantiles equal target quantiles):
  **pinball loss** at τ ∈ {0.1,…,0.9} and **CRPS** approximated by
  `(2/9) Σ_τ pinball_τ` (truncated to the 0.1–0.9 range; D-012). Probabilistic
  baselines: returns → `hist_mean` (historical-simulation quantiles of the training
  window), rv → `har` (point × empirical quantiles of training ratios y/ŷ),
  volume → `har` (point + empirical quantiles of training residuals).
- **Primary loss per target:** returns → MSE; rv → QLIKE; volume → MSE.

## 7. Statistical tests

- **Diebold–Mariano with HAC and HLN correction.** For loss differential `d_t`
  (model − reference) over `T` origins: `DM = d̄ / sqrt(Ω̂/T)`, Ω̂ = Newey–West (Bartlett)
  long-run variance with lag `L = max(q_h, ⌊4 (T/100)^{2/9}⌋)`, where
  `q_h = ⌈h / stride⌉ − 1` is the MA order induced by overlapping targets. HLN factor
  `sqrt((T + 1 − 2k + k(k−1)/T) / T)` with `k = q_h + 1`; p-values from `t_{T−1}`,
  two-sided. If Ω̂ ≤ 0 the lag is reduced to `q_h` (then to 0) and this is flagged.
- **Pooling across assets.** Losses are first normalised per asset by a scale computed
  from **pre-test data only**: MSE → variance of the h-step target before the first
  origin; MAE → mean absolute deviation; QLIKE → 1 (already scale-free); CRPS/pinball →
  pre-test standard deviation. The pooled differential is the cross-sectional mean
  `d̄_t = mean_i d̃_{i,t}` over assets with a forecast at `t`; DM-HLN is applied to
  `d̄_t`. Averaging before the time-series variance estimate keeps cross-sectional
  correlation inside Ω̂.
- **Multiple comparisons.**
  - Primary family (section 8.1, 27 tests): **Holm** step-down at family-wise α = 0.05.
  - Per-asset DM tests: Holm within the family of all per-asset tests.
  - **Model Confidence Set** (Hansen, Lunde & Nason 2011), `T_max` statistic,
    α_MCS = 0.10, stationary bootstrap, B = 1000, expected block length
    `b = max(⌈T^{1/3}⌉, 2(q_h+1))`; run per (target, horizon) on pooled normalised
    losses over the common clean window, and per asset.
- **Effect sizes:** relative loss `mean L_model / mean L_ref` with 95% stationary-bootstrap
  CI is reported next to every test.

## 8. Hypotheses

### 8.1 Primary (confirmatory) family — 27 tests

For each TSFM m (3), target k (3), horizon h (3): H0 `E[d̄_t] = 0` where `d̄_t` is the pooled
normalised primary-loss differential between m and the pre-registered **reference
baseline** (returns: `zero`; rv: `har`; volume: `har`), evaluated on m's **clean window**
(section 9), expanding window. Two-sided DM-HLN, Holm-adjusted at 5%.
"TSFM better" requires `d̄ < 0` and Holm-adjusted p < 0.05.

### 8.2 Secondary (reported with their own corrections)

S1 per-asset DM vs reference; S2 MCS; S3 secondary losses and OOS R²; S4 probabilistic
h=1 (DM-HLN on CRPS vs probabilistic reference, Holm over 9 tests per TSFM family);
S5 rolling-window baselines; S6 contamination test (section 9, Holm over 27);
S7 synthetic control; S8 economic evaluation (illustrative only);
S9 full test period ignoring contamination windows (labelled "possibly contaminated").

## 9. Contamination control

- **Windows per TSFM** (by label, so no target period straddles a boundary):
  - *possibly seen*: origins with `t ≥ 2015-01-02` whose label window ends **before**
    the release date;
  - *clean*: origins with `t ≥ release date + 30 days`;
  - origins in between are excluded from both.
  - The **common clean window** (for MCS) starts at the latest clean start among the
    evaluated TSFMs.
- **Test.** For each (m, k, h), with pooled normalised losses:
  `R_w = Σ_{t∈w} L̄_{m,t} / Σ_{t∈w} L̄_{ref,t}`, `Δ = ln R_clean − ln R_seen`.
  Memorisation predicts Δ > 0 (TSFM relatively better where it may have seen the data).
  95% CI by stationary bootstrap resampling each window independently (block length as
  in section 7, B = 1000); one-sided p-value `P*(Δ* ≤ 0)` under the bootstrap; Holm
  over the 27 tests.
- **Placebo.** The same Δ for baseline-vs-reference pairs that cannot memorise
  (returns: `ar_bic`; rv: `garch`; volume: `ar_bic`) shows how much Δ moves from regime
  differences alone. We call a result "evidence consistent with memorisation" only if
  Δ_m > 0 is Holm-significant **and** Δ_m lies above the placebo's 95% CI.
- **Synthetic control.** Series simulated from GARCH(1,1)-t and HAR-type variance
  processes with intraday Brownian paths (so OHLC and GK exist), plus a two-component
  AR log-volume process with a day-of-week effect. The oracle forecast (true conditional
  expectation) is known. All models run through the same pipeline; losses are reported
  relative to the oracle.

## 10. Reporting commitments and limitations

- All 27 primary results are reported regardless of sign or significance, with effect
  sizes and CIs. Null results are stated as such ("no detectable difference"), not as
  "equal performance".
- The `full` config (larger checkpoints, stride 1, context 2048) is exploratory only.
- Known limitations fixed in advance: survivorship bias of the stock list; GK excludes
  overnight variance; Yahoo data are revised occasionally (hash stored); clean windows are
  short (≈ 1 year for TimesFM 2.5), so power is limited; "possibly seen" windows differ
  from clean windows in market regime, which the placebo only partly controls.

## 11. Amendments

*(none yet)*
