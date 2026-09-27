"""Synthetic control: series no TSFM can have seen, with a known optimal forecast.

1. Calibrate a GARCH(1,1) and a HAR-type variance process on one asset of the panel (the
   economic-evaluation asset, SPY in the default study): GARCH by maximum likelihood with
   normal errors (the simulator's intraday paths are Gaussian), HAR by OLS of next-day GK
   on its 1/5/22-day means (coefficients clipped to be non-negative and scaled to a
   persistence <= 0.95 if necessary; multiplicative shock s.d. fixed at 0.5, D-031).
2. Simulate ``n_series`` assets (alternating GARCH / HAR) with intraday Brownian paths so
   OHLC and Garman-Klass exist, and log volume from the two-component AR process.
3. Run every baseline and TSFM through exactly the same engine.
4. Add an ``oracle`` model: the true conditional expectation of each target given the
   latent state. For rv, the oracle for the GK *proxy* is kappa * E_t[mean sigma2], where
   kappa is the discrete-monitoring factor; ``y_latent`` holds the true mean variance.
"""

from __future__ import annotations

import logging
import warnings

import numpy as np
import pandas as pd

from tsfm_rc.config import RunConfig
from tsfm_rc.data.synthetic import (
    GarchSpec,
    HarSpec,
    VolumeSpec,
    garch_expected_variance,
    gk_discretisation_factor,
    har_expected_variance,
    simulate_asset,
    trading_calendar,
    volume_expected_logvol,
)
from tsfm_rc.data.targets import daily_series, horizon_target
from tsfm_rc.engine.walkforward import qcol, run_baselines
from tsfm_rc.models.features import har_design
from tsfm_rc.seeding import derive_seed

log = logging.getLogger(__name__)


def calibrate(daily: pd.DataFrame) -> tuple[GarchSpec, HarSpec, VolumeSpec]:
    from arch import arch_model

    r = daily["r"].dropna().to_numpy()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = arch_model(r, mean="Constant", vol="GARCH", p=1, q=1, dist="normal", rescale=False).fit(disp="off")
    mu, omega, alpha, beta = (float(x) for x in res.params.to_numpy())
    if alpha + beta >= 0.995:  # keep the simulated process safely stationary
        scale = 0.99 / (alpha + beta)
        alpha, beta = alpha * scale, beta * scale
    g = GarchSpec(omega=omega, alpha=alpha, beta=beta, mu=mu)

    x = np.exp(daily["log_gk_in"])
    X = har_design(x)
    y = x.shift(-1)
    ok = X.notna().all(axis=1) & y.notna()
    A = np.column_stack([np.ones(ok.sum()), X[ok].to_numpy()])
    b, *_ = np.linalg.lstsq(A, y[ok].to_numpy(), rcond=None)
    bd, bw, bm = (max(0.0, float(v)) for v in b[1:])
    pers = bd + bw + bm
    if pers > 0.95:
        bd, bw, bm = (v * 0.95 / pers for v in (bd, bw, bm))
        pers = 0.95
    target_mean = float(x.mean())
    h = HarSpec(c=target_mean * (1 - pers), b_d=bd, b_w=bw, b_m=bm, shock_sd=0.5, mu=mu)

    v = VolumeSpec(level=float(daily["logvol_in"].mean()))
    return g, h, v


def simulate_panel(cfg: RunConfig, specs: tuple[GarchSpec, HarSpec, VolumeSpec]):
    sc = cfg.synthetic
    g, h, v = specs
    dates = trading_calendar("1990-01-01", cfg.data.end)[-sc.n_days :]
    daily, latent, dgp = {}, {}, {}
    for i in range(sc.n_series):
        spec = g if i % 2 == 0 else h
        name = f"SIM_{'GARCH' if i % 2 == 0 else 'HAR'}_{i:02d}"
        rng = np.random.default_rng(derive_seed(cfg.seed, "synthetic_control", i))
        ohlcv, lat = simulate_asset(spec, v, dates, rng, steps=sc.intraday_steps)
        daily[name] = daily_series(ohlcv)
        latent[name] = lat
        dgp[name] = spec
    return daily, latent, dgp, dates


def synthetic_config(cfg: RunConfig, dates: pd.DatetimeIndex) -> RunConfig:
    sc = cfg.synthetic
    test_start = dates[sc.n_days - sc.test_days].date()
    ev = cfg.evaluation.model_copy(
        update={"test_start": test_start, "windows": ["expanding"], "primary_window": "expanding",
                "min_train_obs": min(cfg.evaluation.min_train_obs, sc.n_days - sc.test_days - 1)}
    )
    data = cfg.data.model_copy(update={"start": dates[0].date(), "end": dates[-1].date()})
    tg = cfg.targets.model_copy(update={"horizons": sorted(sc.horizons)})
    return cfg.model_copy(update={"evaluation": ev, "data": data, "targets": tg})


def oracle_rows(fc: pd.DataFrame, daily, latent, dgp, vspec: VolumeSpec, cfg: RunConfig) -> pd.DataFrame:
    """Oracle forecasts on the same (ticker, target, origin, horizon) grid as ``fc``."""
    kappa = gk_discretisation_factor(cfg.synthetic.intraday_steps)
    grid = fc[fc["window"] == "expanding"].drop_duplicates(["ticker", "target", "origin", "horizon"])
    rows = []
    for r in grid.itertuples(index=False):
        spec = dgp[r.ticker]
        d = daily[r.ticker]
        lat = latent[r.ticker]
        pos = d.index.get_loc(r.asset_date)
        h = int(r.horizon)
        if r.target == "returns":
            pred = h * spec.mu
        elif r.target == "rv":
            if isinstance(spec, GarchSpec):
                path = garch_expected_variance(spec, np.array(lat["sigma2_next"].iloc[pos]), h)
            else:
                path = har_expected_variance(spec, lat["sigma2"].to_numpy()[: pos + 1], h)
            pred = kappa * float(np.mean(path))
        else:
            fut = d.index[pos + 1 : pos + 1 + h]
            if len(fut) < h:
                fut = pd.DatetimeIndex([r.asset_date + pd.offsets.BDay(i) for i in range(1, h + 1)])
            pred = float(np.mean(volume_expected_logvol(vspec, lat["vol_fast"].iloc[pos], lat["vol_slow"].iloc[pos], fut)))
        row = r._asdict()
        row.update({"model": "oracle", "y_pred": float(pred), "refit": False, "flag": "", "n_train": pos + 1})
        for c in [c for c in row if c.startswith("q") and c[1:].isdigit()]:
            row[c] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def add_latent_truth(fc: pd.DataFrame, latent: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Column ``y_latent``: the true mean variance over the h-step window (rv rows only)."""
    fc = fc.copy()
    fc["y_latent"] = np.nan
    for t, lat in latent.items():
        for h in fc["horizon"].unique():
            tv = horizon_target(lat["sigma2"], int(h), "mean")
            m = (fc["ticker"] == t) & (fc["target"] == "rv") & (fc["horizon"] == h)
            fc.loc[m, "y_latent"] = tv.reindex(fc.loc[m, "asset_date"]).to_numpy()
    return fc


def run_synthetic_control(cfg: RunConfig, calib_daily: pd.DataFrame, *, run_tsfms_fn=None) -> tuple[pd.DataFrame, dict]:
    specs = calibrate(calib_daily)
    daily, latent, dgp, dates = simulate_panel(cfg, specs)
    scfg = synthetic_config(cfg, dates)
    parts = [run_baselines(daily, dates, scfg)]
    status: dict = {}
    if run_tsfms_fn is not None:
        tfc, status = run_tsfms_fn(daily, dates, scfg)
        if len(tfc):
            parts.append(tfc)
    fc = pd.concat(parts, ignore_index=True)
    fc = pd.concat([fc, oracle_rows(fc, daily, latent, dgp, specs[2], scfg)], ignore_index=True)
    fc = add_latent_truth(fc, latent)
    for lv in cfg.stats.quantile_levels:
        if qcol(lv) not in fc.columns:
            fc[qcol(lv)] = np.nan
    meta = {
        "garch_spec": specs[0].__dict__, "har_spec": specs[1].__dict__, "volume_spec": specs[2].__dict__,
        "kappa": gk_discretisation_factor(cfg.synthetic.intraday_steps), "tsfm_status": status,
        "n_series": cfg.synthetic.n_series, "n_days": cfg.synthetic.n_days, "test_days": cfg.synthetic.test_days,
    }
    return fc, meta
