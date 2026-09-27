"""Classical baselines (PREREGISTRATION.md section 5.1). Strong, cheap, fixed in advance.

| name            | targets          | idea                                                         |
|-----------------|------------------|--------------------------------------------------------------|
| zero            | returns          | forecast 0 (random walk in log price)                        |
| hist_mean       | returns          | h x mean past return; historical-simulation quantiles        |
| ar_bic          | returns, volume  | AR(p), p in 0..10 by BIC on the window, iterated to h        |
| ewma            | rv               | RiskMetrics lambda = 0.94, flat, proxy-aligned               |
| garch/gjr_garch | rv               | GARCH(1,1)/GJR(1,1,1), Student-t, analytic h-step, aligned   |
| har             | rv, volume       | direct OLS on 1/5/22-day means (Corsi 2009)                  |
| seasonal_naive  | volume           | last value on the same weekday                               |
| lgbm            | all              | direct LightGBM per horizon on causal features               |

"Proxy-aligned" (DECISIONS.md D-007, PREREGISTRATION.md amendment A3): return-based variance
forecasts are multiplied by ``c = mean_t(GK_t / s2_t)``, where ``s2_t`` is the model's own
in-sample one-step-ahead variance for day t over the training window. This is the
QLIKE-optimal constant rescaling of the model's forecasts; it is needed because the target
is open-to-close GK variance while GARCH/EWMA model close-to-close returns. (The original
``mean(GK)/mean(r^2)`` was replaced because a single jump day dominates it.)
"""

from __future__ import annotations

import logging
import warnings
from collections.abc import Sequence

import numpy as np
import pandas as pd
from scipy.linalg import solve_triangular
from scipy.signal import lfilter
from scipy.stats import norm

from tsfm_rc.models.base import (
    Forecast,
    Forecaster,
    PointForecast,
    QuantileForecast,
    daily_target_series,
    ols,
    training_labels,
)
from tsfm_rc.models.features import har_design, lgbm_features

log = logging.getLogger(__name__)


def _agg(path: np.ndarray, kind: str, h: int) -> float:
    p = np.asarray(path[:h], dtype=float)
    return float(p.sum() if kind == "returns" else p.mean())


def _levels_tuple(levels: Sequence[float] | None) -> tuple[float, ...]:
    return tuple(float(q) for q in levels) if levels else ()


def proxy_alignment(gk: np.ndarray, fitted_var: np.ndarray, burn: int = 22) -> float:
    """QLIKE-optimal scale c = mean(GK_t / s2_t) over the training window (amendment A3).

    ``fitted_var[t]`` must be the model's variance forecast for day t made at t-1 (in-sample,
    one step ahead). The first ``burn`` days (filter warm-up) are skipped. Minimising
    sum_t QLIKE(GK_t, c s2_t) over c gives exactly this mean.
    """
    gk = np.asarray(gk, float)[burn:]
    fv = np.asarray(fitted_var, float)[burn:]
    ok = np.isfinite(gk) & np.isfinite(fv) & (fv > 0) & (gk > 0)
    if ok.sum() < 20:
        return 1.0
    return float(np.mean(gk[ok] / fv[ok]))


# ============================================================== returns


class Zero(Forecaster):
    name = "zero"
    kinds = ("returns",)

    def fit(self, history):
        self.fitted = True

    def predict(self, history, horizons, quantile_levels=None):
        return Forecast(PointForecast({h: 0.0 for h in horizons}))


class HistMean(Forecaster):
    name = "hist_mean"
    kinds = ("returns",)

    def fit(self, history):
        r = history["r"].dropna().to_numpy()
        self.mu = float(r.mean())
        self.sample = r
        self.fitted = True

    def predict(self, history, horizons, quantile_levels=None):
        pf = PointForecast({h: h * self.mu for h in horizons})
        qf = None
        if quantile_levels and 1 in horizons:
            lv = _levels_tuple(quantile_levels)
            qf = QuantileForecast(lv, {1: np.quantile(self.sample, lv)})
        return Forecast(pf, qf)


# ============================================================== AR with BIC


def ar_bic_select(x: np.ndarray, pmax: int) -> tuple[int, np.ndarray, float]:
    """Select AR order p in {0..pmax} by BIC on a common sample; return (p, beta, sigma2).

    One QR decomposition of the full lag matrix gives the residual sum of squares of
    every nested model: RSS_p = y'y - ||Q_{:, :p+1}' y||^2.
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x) - pmax
    if n <= 3 * (pmax + 1):
        raise ValueError("series too short for AR selection")
    Y = x[pmax:]
    X = np.column_stack([np.ones(n)] + [x[pmax - j : len(x) - j] for j in range(1, pmax + 1)])
    Q, R = np.linalg.qr(X)
    qy = Q.T @ Y
    rss = np.maximum(Y @ Y - np.cumsum(qy**2), 1e-300)  # rss[k] uses first k+1 columns
    k = np.arange(1, pmax + 2)
    bic = n * np.log(rss / n) + k * np.log(n)
    p = int(np.argmin(bic))
    beta = solve_triangular(R[: p + 1, : p + 1], qy[: p + 1])
    sigma2 = float(rss[p] / (n - p - 1))
    return p, beta, sigma2


def ar_iterate(x_hist: np.ndarray, beta: np.ndarray, steps: int) -> np.ndarray:
    p = len(beta) - 1
    buf = list(np.asarray(x_hist, dtype=float)[-p:]) if p > 0 else []
    out = np.empty(steps)
    for i in range(steps):
        val = beta[0] + sum(beta[j] * buf[-j] for j in range(1, p + 1))
        out[i] = val
        if p > 0:
            buf.append(val)
    return out


class ARBIC(Forecaster):
    name = "ar_bic"
    kinds = ("returns", "volume")

    def __init__(self, kind, seed=0, pmax: int = 10):
        super().__init__(kind, seed)
        self.pmax = pmax

    def fit(self, history):
        x = daily_target_series(history, self.kind).to_numpy()
        self.p, self.beta, self.sigma2 = ar_bic_select(x, self.pmax)
        self.fitted = True

    def predict(self, history, horizons, quantile_levels=None):
        x = daily_target_series(history, self.kind).dropna().to_numpy()
        path = ar_iterate(x, self.beta, max(horizons))
        pf = PointForecast({h: _agg(path, self.kind, h) for h in horizons})
        qf = None
        if quantile_levels and 1 in horizons:
            lv = _levels_tuple(quantile_levels)
            qf = QuantileForecast(lv, {1: path[0] + np.sqrt(self.sigma2) * norm.ppf(lv)})
        return Forecast(pf, qf, {"p": self.p})


# ============================================================== volatility


def ewma_filter(r: np.ndarray, lam: float) -> np.ndarray:
    """One-step EWMA variances: out[t] = forecast for day t made at t-1; out[n] = next day.

    sigma2_{t+1} = lam sigma2_t + (1 - lam) r_t^2, initialised at mean(r^2) of the first 22 obs.
    """
    s0 = float(np.mean(r[:22] ** 2))
    y, _ = lfilter([1.0 - lam], [1.0, -lam], r**2, zi=[lam * s0])
    return np.concatenate([[s0], y])


def ewma_next_variance(r: np.ndarray, lam: float) -> float:
    r = r[np.isfinite(r)]
    return float(ewma_filter(r, lam)[-1])


def _gk_and_r(history: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Aligned arrays of GK and returns on days where the return exists."""
    ok = history["r"].notna()
    return history.loc[ok, "gk"].to_numpy(float), history.loc[ok, "r"].to_numpy(float)


class EWMA(Forecaster):
    name = "ewma"
    kinds = ("rv",)

    def __init__(self, kind, seed=0, lam: float = 0.94):
        super().__init__(kind, seed)
        self.lam = lam

    def fit(self, history):
        self.fitted = True

    def predict(self, history, horizons, quantile_levels=None):
        gk, r = _gk_and_r(history)
        path = ewma_filter(r, self.lam)  # path[t] = one-step variance for day t; path[-1] = next day
        c = proxy_alignment(gk, path[:-1])
        return Forecast(PointForecast({h: c * float(path[-1]) for h in horizons}), meta={"c": c})


class GARCH(Forecaster):
    """GARCH(1,1) (o=0) or GJR-GARCH(1,1,1) (o=1), constant mean, Student-t errors."""

    name = "garch"
    kinds = ("rv",)
    o = 0

    def __init__(self, kind, seed=0, lam_fallback: float = 0.94):
        super().__init__(kind, seed)
        self.params: np.ndarray | None = None
        self.lam_fallback = lam_fallback
        self.n_failed_fits = 0

    def _model(self, r: np.ndarray):
        from arch import arch_model

        return arch_model(r, mean="Constant", vol="GARCH", p=1, o=self.o, q=1, dist="t", rescale=False)

    def fit(self, history):
        r = history["r"].dropna().to_numpy()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                res = self._model(r).fit(disp="off", options={"maxiter": 1000})
                ok = res.convergence_flag == 0 and np.all(np.isfinite(res.params.to_numpy()))
            except Exception as e:  # pragma: no cover - rare optimiser failure
                log.debug("%s fit failed: %s", self.name, e)
                ok = False
        if ok:
            self.params = res.params.to_numpy()
        else:
            self.n_failed_fits += 1  # keep previous parameters if we have them
        self.fitted = True

    def predict(self, history, horizons, quantile_levels=None):
        gk, r = _gk_and_r(history)
        H = max(horizons)
        if self.params is None:  # never converged: fall back to EWMA, flagged
            ew = ewma_filter(r, self.lam_fallback)
            c = proxy_alignment(gk, ew[:-1])
            return Forecast(PointForecast({h: c * float(ew[-1]) for h in horizons}), meta={"fallback": "ewma", "c": c})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fixed = self._model(r).fix(self.params)
            in_sample = np.asarray(fixed.conditional_volatility, float) ** 2  # s2_t given t-1
            path = fixed.forecast(horizon=H, reindex=False).variance.to_numpy()[-1]
        c = proxy_alignment(gk, in_sample)
        return Forecast(PointForecast({h: c * float(np.mean(path[:h])) for h in horizons}), meta={"c": c})


class GJRGARCH(GARCH):
    name = "gjr_garch"
    o = 1


class HAR(Forecaster):
    """Direct HAR regression per horizon (rv: GK levels; volume: log volume)."""

    name = "har"
    kinds = ("rv", "volume")

    def __init__(self, kind, seed=0, horizons: Sequence[int] = (1, 5, 20)):
        super().__init__(kind, seed)
        self.horizons = tuple(horizons)

    def fit(self, history):
        x = daily_target_series(history, self.kind)
        X = har_design(x)
        self.beta: dict[int, np.ndarray] = {}
        self.resid_q: dict[int, np.ndarray] = {}
        self.floor = 0.01 * float(history["gk"].mean()) if self.kind == "rv" else -np.inf
        for h in self.horizons:
            y = training_labels(history, self.kind, h)
            ok = X.notna().all(axis=1) & y.notna()
            A = np.column_stack([np.ones(ok.sum()), X[ok].to_numpy()])
            b = ols(A, y[ok].to_numpy())
            self.beta[h] = b
            if h == 1:
                fitted = A @ b
                if self.kind == "rv":
                    pos = fitted > 0
                    self.resid_q[h] = y[ok].to_numpy()[pos] / fitted[pos]  # multiplicative
                else:
                    self.resid_q[h] = y[ok].to_numpy() - fitted  # additive
        self.fitted = True

    def predict(self, history, horizons, quantile_levels=None):
        X = har_design(daily_target_series(history, self.kind))
        x_t = np.concatenate([[1.0], X.iloc[-1].to_numpy()])
        pts = {h: float(max(self.floor, x_t @ self.beta[h])) for h in horizons}
        qf = None
        if quantile_levels and 1 in horizons and 1 in self.resid_q:
            lv = _levels_tuple(quantile_levels)
            e = np.quantile(self.resid_q[1], lv)
            q = pts[1] * e if self.kind == "rv" else pts[1] + e
            qf = QuantileForecast(lv, {1: q})
        return Forecast(PointForecast(pts), qf)


# ============================================================== volume


class SeasonalNaive(Forecaster):
    """Per step, the most recent log volume observed on the same weekday."""

    name = "seasonal_naive"
    kinds = ("volume",)

    def fit(self, history):
        self.fitted = True

    def predict(self, history, horizons, quantile_levels=None):
        lv = history["logvol_in"]
        last_by_dow = lv.groupby(history["dow"]).last()
        t = history.index[-1]
        H = max(horizons)
        future = [t + pd.offsets.BDay(i) for i in range(1, H + 1)]
        path = np.array([last_by_dow.get(d.dayofweek, lv.iloc[-1]) for d in future], dtype=float)
        return Forecast(PointForecast({h: float(path[:h].mean()) for h in horizons}))


# ============================================================== LightGBM


class LGBM(Forecaster):
    name = "lgbm"
    kinds = ("returns", "rv", "volume")

    def __init__(self, kind, seed=0, horizons: Sequence[int] = (1, 5, 20), params: dict | None = None):
        super().__init__(kind, seed)
        self.horizons = tuple(horizons)
        self.params = dict(params or {})

    def _native_params(self) -> tuple[dict, int]:
        """Map the sklearn-style names in the config to LightGBM's native API."""
        p = self.params
        native = {
            "objective": "regression",
            "learning_rate": p.get("learning_rate", 0.05),
            "num_leaves": p.get("num_leaves", 15),
            "min_data_in_leaf": p.get("min_child_samples", 50),
            "bagging_fraction": p.get("subsample", 0.8),
            "bagging_freq": p.get("subsample_freq", 1),
            "feature_fraction": p.get("colsample_bytree", 0.8),
            "lambda_l2": p.get("reg_lambda", 1.0),
            "seed": self.seed,
            "deterministic": True,
            "force_row_wise": True,
            "num_threads": 1,
            "verbose": -1,
        }
        return native, int(p.get("n_estimators", 200))

    def fit(self, history):
        import lightgbm as lgb

        F = lgbm_features(history, self.kind)
        self.models = {}
        self.floor = 0.01 * float(history["gk"].mean()) if self.kind == "rv" else -np.inf
        params, n_rounds = self._native_params()
        for h in self.horizons:
            y = training_labels(history, self.kind, h)
            ok = y.notna() & F.notna().all(axis=1)
            ds = lgb.Dataset(F[ok].to_numpy(), y[ok].to_numpy(), params={"verbose": -1})
            self.models[h] = lgb.train(params, ds, num_boost_round=n_rounds)
        self.fitted = True

    def predict(self, history, horizons, quantile_levels=None):
        F = lgbm_features(history, self.kind)
        x = F.iloc[[-1]].to_numpy()
        return Forecast(PointForecast({h: float(max(self.floor, self.models[h].predict(x)[0])) for h in horizons}))


BASELINE_CLASSES: dict[str, type[Forecaster]] = {
    c.name: c for c in (Zero, HistMean, ARBIC, EWMA, GARCH, GJRGARCH, HAR, SeasonalNaive, LGBM)
}
