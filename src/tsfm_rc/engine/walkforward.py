"""Walk-forward engine (expanding and rolling windows).

For every (asset, target, window) task and every baseline, the engine walks through the
forecast origins in order. At each origin it:

1. cuts the asset's daily frame with ``origin.history`` (rows <= t only);
2. for the rolling variant keeps only the last ``rolling_length`` rows;
3. re-fits the model if the re-fit schedule says so (every k *usable* origins);
4. asks for forecasts for all horizons at once and records them next to the realised
   target (the target is looked up afterwards and never shown to the model).

Output: one row per (asset, target, model, window, origin, horizon) in a long DataFrame
with the quantile columns q10..q90 filled for h = 1 where the model provides them.

Two passes use this engine (amendment A4):

- the **main pass**: every baseline, both windows, origins every ``evaluation.stride`` days
  over the whole test period (all secondary analyses, the possibly-seen side);
- the **primary pass**: only the reference and placebo baselines, expanding window, origins
  every ``evaluation.primary_stride`` (= 1) day from the earliest possible clean-window start.
  Re-fit intervals are rescaled to the same number of trading days (DECISIONS D-040), and
  the main pass is not touched, so every secondary table is unchanged by A4.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
import time
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import numpy as np
import pandas as pd

from tsfm_rc.config import RunConfig
from tsfm_rc.data.targets import make_target
from tsfm_rc.models.registry import make_baseline, refit_every
from tsfm_rc.origin import ForecastOrigin, make_origin_schedule
from tsfm_rc.seeding import derive_seed

log = logging.getLogger(__name__)

MAX_STALENESS_DAYS = 10  # skip an origin if the asset's last row is older than this


def qcol(level: float) -> str:
    return f"q{int(round(level * 100)):02d}"


FORECAST_COLUMNS = [
    "ticker", "target", "model", "window", "origin", "asset_date", "ordinal",
    "horizon", "label_end", "y_true", "y_pred", "n_train", "refit", "flag",
]


def label_end_date(index: pd.DatetimeIndex, asset_date: pd.Timestamp, h: int) -> pd.Timestamp:
    """Date of the last day in the h-step label window (the asset's h-th trading day after
    ``asset_date``), or NaT if that day is beyond the data. Used for contamination windows."""
    pos = int(index.searchsorted(asset_date, side="left")) + h
    return index[pos] if pos < len(index) else pd.NaT


@dataclass(frozen=True)
class Task:
    ticker: str
    kind: str
    window: str
    models: tuple[str, ...]
    stride: int | None = None  # None = main schedule (evaluation.stride)


def build_origins(calendar: pd.DatetimeIndex, cfg: RunConfig) -> list[ForecastOrigin]:
    ev = cfg.evaluation
    # min_train_obs is enforced per asset in the loop; the schedule starts at test_start.
    return make_origin_schedule(calendar, ev.test_start, ev.stride, min_train_obs=1, end=cfg.data.end)


def primary_pass_start(cfg: RunConfig) -> pd.Timestamp:
    """Earliest possible clean-window start over the configured TSFMs: documented release date
    + buffer. The effective release (A1) is never earlier than the documented one, so every
    model's actual clean window lies inside [this date, end]."""
    buffer = pd.Timedelta(days=cfg.contamination.buffer_days)
    starts = [pd.Timestamp(s.release_date) + buffer for s in cfg.models.tsfms]
    test_start = pd.Timestamp(cfg.evaluation.test_start)
    return max(test_start, min(starts)) if starts else test_start


def build_primary_origins(calendar: pd.DatetimeIndex, cfg: RunConfig, start: pd.Timestamp | None = None) -> list[ForecastOrigin]:
    """Stride-``primary_stride`` origins from ``start`` (default: :func:`primary_pass_start`)."""
    start = primary_pass_start(cfg) if start is None else max(pd.Timestamp(start), pd.Timestamp(cfg.evaluation.test_start))
    return make_origin_schedule(calendar, start, cfg.evaluation.primary_stride, min_train_obs=1, end=cfg.data.end)


def primary_pass_models(cfg: RunConfig, kind: str) -> tuple[str, ...]:
    """Baselines needed on stride-1 clean-window origins: the reference (primary family) and
    the placebo models (clean side of the contamination test)."""
    names = [cfg.models.reference[kind], *cfg.contamination.placebo_pairs.get(kind, [])]
    return tuple(dict.fromkeys(n for n in names if n in cfg.models.baselines[kind]))


def window_slice(hist: pd.DataFrame, window: str, cfg: RunConfig) -> pd.DataFrame:
    if window == "rolling":
        return hist.iloc[-cfg.evaluation.rolling_length :]
    return hist


def run_task(daily: pd.DataFrame, task: Task, origins: Sequence[ForecastOrigin], cfg: RunConfig) -> pd.DataFrame:
    horizons = cfg.targets.horizons
    levels = cfg.stats.quantile_levels
    targets = {h: make_target(daily, task.kind, h) for h in horizons}
    rows: list[dict] = []
    for name in task.models:
        seed = derive_seed(cfg.seed, task.ticker, task.kind, task.window, name)
        model = make_baseline(name, task.kind, cfg, seed)
        k_refit = refit_every(name, cfg, task.stride)
        since_fit = None
        t0 = time.time()
        for o in origins:
            hist = o.history(daily)
            if len(hist) < cfg.evaluation.min_train_obs:
                continue
            asset_date = hist.index[-1]
            if (o.timestamp - asset_date).days > MAX_STALENESS_DAYS:
                continue
            hist = window_slice(hist, task.window, cfg)
            o.assert_no_future(hist)
            refit = since_fit is None or since_fit >= k_refit
            if refit:
                model.fit(hist)
                since_fit = 0
            fc = model.predict(hist, horizons, levels)
            since_fit += 1
            for h in horizons:
                row = {
                    "ticker": task.ticker, "target": task.kind, "model": name, "window": task.window,
                    "origin": o.timestamp, "asset_date": asset_date, "ordinal": o.ordinal,
                    "horizon": h, "label_end": label_end_date(daily.index, asset_date, h),
                    "y_true": float(targets[h].get(asset_date, np.nan)),
                    "y_pred": float(fc.point[h]), "n_train": len(hist), "refit": refit,
                    "flag": str(fc.meta.get("fallback", "")),
                }
                if fc.quantiles is not None and h in fc.quantiles.values:
                    for lv, v in zip(fc.quantiles.levels, fc.quantiles.values[h], strict=True):
                        row[qcol(lv)] = float(v)
                rows.append(row)
        log.debug("%s %s %s %s: %.1fs", task.ticker, task.kind, task.window, name, time.time() - t0)
    df = pd.DataFrame(rows)
    for lv in levels:
        if qcol(lv) not in df.columns:
            df[qcol(lv)] = np.nan
    return df


def _run_task_star(args) -> pd.DataFrame:
    return run_task(*args)


def run_baselines(daily: dict[str, pd.DataFrame], calendar: pd.DatetimeIndex, cfg: RunConfig, n_jobs: int | None = None) -> pd.DataFrame:
    """Main pass: every configured baseline for every asset, target and window."""
    origins = build_origins(calendar, cfg)
    tasks = [
        Task(t, kind, window, tuple(cfg.models.baselines[kind]))
        for t in daily
        for kind in cfg.targets.kinds
        for window in cfg.evaluation.windows
    ]
    return _run_tasks(daily, tasks, origins, cfg, n_jobs)


def run_primary_baselines(daily: dict[str, pd.DataFrame], calendar: pd.DatetimeIndex, cfg: RunConfig, n_jobs: int | None = None) -> pd.DataFrame:
    """Primary pass (A4): reference + placebo baselines, expanding window, stride-1 origins."""
    origins = build_primary_origins(calendar, cfg)
    tasks = [
        Task(t, kind, cfg.evaluation.primary_window, primary_pass_models(cfg, kind), stride=cfg.evaluation.primary_stride)
        for t in daily
        for kind in cfg.targets.kinds
    ]
    return _run_tasks(daily, tasks, origins, cfg, n_jobs)


def _run_tasks(daily: dict[str, pd.DataFrame], tasks: list[Task], origins: list[ForecastOrigin], cfg: RunConfig,
               n_jobs: int | None) -> pd.DataFrame:
    n_jobs = n_jobs or cfg.n_jobs
    log.info("walk-forward: %d tasks, %d origins, n_jobs=%d", len(tasks), len(origins), n_jobs)
    args = [(daily[t.ticker], t, origins, cfg) for t in tasks]
    if n_jobs > 1:
        # One BLAS/OpenMP thread per worker (spawned children read these at import time);
        # otherwise n_jobs processes x all-core BLAS threads oversubscribe the CPU.
        for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
            os.environ.setdefault(var, "1")
        # 'spawn', not 'fork': forking after LightGBM/OpenMP threads exist can deadlock
        with ProcessPoolExecutor(max_workers=n_jobs, mp_context=mp.get_context("spawn")) as ex:
            parts = list(ex.map(_run_task_star, args))
    else:
        parts = [_run_task_star(a) for a in args]
    out = pd.concat([p for p in parts if len(p)], ignore_index=True)
    sort_cols = ["target", "ticker", "model", "window", "horizon", "origin"]
    return out.sort_values(sort_cols, kind="stable").reset_index(drop=True)
