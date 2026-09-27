# [Title: a claim-free, descriptive title]
*Do pretrained time-series foundation models forecast financial returns, volatility and volume better than classical baselines?*

**Abstract (≤ 150 words).** Question · data (real, universe, period) · models · design
(walk-forward, pre-registered, contamination control) · the primary result in one sentence
with corrected p-values · the main limitation.

## 1. Introduction (≈ 0.5 page)
Why the question matters; what TSFMs are; why an honest evaluation needs walk-forward
testing, multiple-testing control and a contamination check. End with the contribution in
2–3 bullet points.

## 2. Data (≈ 0.5 page)
Source, period (2000-01-03 to 2026-09-25), universe and why (survivorship bias!), cleaning
summary (from `results/default/cleaning_report.csv`), targets: log returns, Garman–Klass
variance, log volume; horizons 1, 5, 20.

## 3. Method (≈ 1 page)
3.1 Forecast origins, windows, no look-ahead (`ForecastOrigin`, leakage tests).
3.2 Baselines (table), TSFMs (checkpoints, context 512, zero-shot, input transformations).
3.3 Losses (MSE, QLIKE, CRPS/pinball), DM-HLN with HAC (amendment A2), pooling, Holm, MCS.
3.4 Contamination windows, the Δ statistic, placebo, synthetic control.
3.5 Pre-registration and the dated amendments A1–A3 (what changed, why, what had been seen).

## 4. Results (≈ 1.5 pages)
4.1 Primary family: the 27-row table (generated), one paragraph.
4.2 Model Confidence Sets.
4.3 Contamination test and placebo.
4.4 Synthetic control.
4.5 Robustness: rolling window, per-asset, probabilistic.
4.6 Economic illustration (clearly labelled illustrative).

## 5. Discussion and limitations (≈ 0.5 page)
What the evidence does and does not show; power (length of clean windows); contamination
uncertainty (cite `docs/PRETRAINING-DATA.md` tags); survivorship; volatility proxy.

## 6. Reproducibility statement
Repository commit, `make reproduce`, lockfile, data and config hashes (from the report's
Provenance section).

## References
Only papers you have read. Core: Diebold & Mariano (1995); Harvey, Leybourne & Newbold (1997);
Newey & West (1987, 1994); Hansen, Lunde & Nason (2011); Patton (2011); Garman & Klass (1980);
Corsi (2009); Campbell & Thompson (2008); Politis & Romano (1994); Holm (1979); the Chronos,
TimesFM and Moirai papers.
