# TSFM Reality Check

An honest, reproducible benchmark of pretrained **time-series foundation models**
(Chronos-Bolt, TimesFM 2.5, Moirai 1.1) against **strong classical baselines** (AR, GARCH,
GJR-GARCH, HAR, EWMA, LightGBM, naive rules) on daily **returns**, **realised volatility** and
**trading volume** of 26 US ETFs and large caps, with strict walk-forward evaluation,
Diebold–Mariano tests with HAC variance, multiple-testing control, a Model Confidence Set,
and an explicit **pretraining-contamination** test. Plus a **website** with eleven lessons
(Python runs in your browser), the results dashboard, spaced-repetition review and synced
progress, so the terminal is only needed for the heavy experiments.

