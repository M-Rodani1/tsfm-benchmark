# Glossary

Short definitions of terms used in the code, docs and lessons. The lesson that teaches
each term properly is in brackets.

| Term | Meaning |
|---|---|
| **Adjusted close** | Closing price corrected for splits and dividends, so returns across those events are economically meaningful. [L01] |
| **AR(p)** | Autoregressive model: today's value is a linear function of the previous p values plus noise. [L04] |
| **BIC** | Bayesian information criterion; picks model complexity by trading fit against number of parameters. Computed on training data only. [L04] |
| **Block bootstrap** | Resampling blocks of consecutive observations (not single points) so that autocorrelation survives the resampling. [L07] |
| **Clean window** | Test period starting after a TSFM's public release (+30 days); the model cannot have seen these data during pretraining. [L08] |
| **Context length** | Number of past observations fed to a foundation model (512 here). [L05] |
| **Contamination** | When evaluation data were part of a model's training data, so good scores may reflect memorisation. [L08] |
| **CRPS** | Continuous ranked probability score; a proper scoring rule for a whole predictive distribution. Here approximated from nine quantiles. [L06] |
| **Diebold–Mariano (DM) test** | Tests whether two forecasts have equal expected loss, using the time series of loss differences. [L07] |
| **Direct forecast** | A separate model is trained for each horizon h to predict the h-step target directly. Contrast: iterated. [L04] |
| **EWMA** | Exponentially weighted moving average of squared returns (RiskMetrics λ = 0.94). [L04] |
| **Expanding window** | Training data grow over time: everything from the start up to the origin. [L03] |
| **Forecast origin** | The time t at which a forecast is made; only data up to t may be used. `ForecastOrigin` in code. [L03] |
| **Garman–Klass (GK)** | Range-based daily variance estimator from open, high, low, close. [L02] |
| **GARCH(1,1)** | Model where today's variance depends on yesterday's squared return and yesterday's variance. [L04] |
| **GJR-GARCH** | GARCH with an extra term for negative returns (leverage effect). [L04] |
| **Fixed-b (Kiefer–Vogelsang) test** | A DM-type t-test whose long-run variance uses a bandwidth that is a fixed fraction b of the sample (here b = 1, i.e. all lags, Bartlett weights) and whose critical values come from its own non-normal limit (5% two-sided: 4.771). Better size than HAC + normal/t critical values when data overlap heavily; used for the primary family (amendment A4). [L07] |
| **HAC** | Heteroskedasticity- and autocorrelation-consistent variance estimator (Newey–West). [L07] |
| **HAR** | Heterogeneous autoregression (Corsi 2009): regress future variance on daily, weekly and monthly averages. [L04] |
| **HLN correction** | Harvey–Leybourne–Newbold small-sample adjustment to the DM statistic, compared with a t distribution. [L07] |
| **Holm correction** | Step-down method controlling the family-wise error rate across many tests. [L07] |
| **Horizon (h)** | How many trading days ahead the target lies (1, 5, 20). [L01] |
| **Leakage / look-ahead bias** | Any use of information from after the forecast origin. [L03] |
| **LightGBM** | Gradient-boosted decision trees; our flexible machine-learning baseline. [L04] |
| **Log return** | `ln(C_t / C_{t-1})`; adds up over time. We use percent (×100). [L01] |
| **MCS** | Model Confidence Set: the set of models that cannot be statistically distinguished from the best. [L07] |
| **Memorisation** | A model reproducing training data it has seen rather than forecasting. [L08] |
| **MSE / MAE** | Mean squared / absolute error. [L06] |
| **OOS R²** | Out-of-sample R²: 1 minus the ratio of a model's MSE to a benchmark's MSE. Negative = worse than benchmark. [L06] |
| **Pinball loss** | Loss for a quantile forecast; asymmetric absolute error. [L06] |
| **Placebo test** | Running the contamination test on models that cannot memorise, to see how much the statistic moves by chance/regime. [L08] |
| **Pooled test** | Test on the cross-sectional average loss differential across assets. [L07] |
| **Possibly-seen window** | Test period whose targets ended before a TSFM's release. [L08] |
| **Pre-registration** | Writing down the analysis plan before seeing results. `docs/PREREGISTRATION.md`. [L03] |
| **QLIKE** | Loss for variance forecasts, `y/ŷ − ln(y/ŷ) − 1`; robust to noise in the variance proxy. [L06] |
| **Quantile forecast** | A forecast of the value below which the outcome falls with probability τ. [L05] |
| **Realised volatility (RV)** | A measured (not modelled) estimate of past variance; here GK variance averaged over h days. [L02] |
| **Rolling window** | Training data of fixed length (1000 days) that slides forward. [L03] |
| **Primary pass** | The second forecasting pass added by amendment A4: origins every trading day (stride 1) inside the TSFMs' clean windows, only for the primary family and the clean side of the contamination test. [L07] |
| **Stride** | Trading days between consecutive forecast origins: 5 in the main pass, 1 in the primary pass (A4). [L03] |
| **Survivorship bias** | Studying only assets that survived to today. [L09] |
| **Synthetic control** | Simulated series with known dynamics that no TSFM can have seen. [L08] |
| **TSFM** | Time-series foundation model: a large neural network pretrained on many series, used zero-shot. [L05] |
| **UNAVAILABLE** | Marker used everywhere when a model could not be installed or downloaded. No numbers are shown for it. [L05] |
| **Walk-forward evaluation** | Repeatedly: fit on the past, forecast the future, move the origin forward. [L03] |
| **Zero-shot** | Using a pretrained model on new data without any training on it. [L05] |
