"""Batched zero-shot TSFM forecasting with an on-disk output cache.

Cache key (SHA-256 of canonical JSON) = model name, HF id, resolved weight revision,
package version, series (ticker), target kind, origin, steps, context length, and the
SHA-256 of the exact context array fed to the model (the most precise "data hash": if
the input changes in any digit, the key changes). Values stored: per-step medians and
deciles. Reruns only compute what is missing.

Layout: ``cache/tsfm/<model>/<ticker>__<kind>.parquet``.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from tsfm_rc.config import RunConfig, TSFMSpec
from tsfm_rc.data.targets import make_target
from tsfm_rc.engine.walkforward import (
    MAX_STALENESS_DAYS,
    build_origins,
    build_primary_origins,
    label_end_date,
    qcol,
)
from tsfm_rc.hashing import sha256_array, sha256_json
from tsfm_rc.models.tsfm import (
    DECILES,
    TSFMBackend,
    TSFMUnavailable,
    load_backend,
    make_context,
    to_target_scale,
)
from tsfm_rc.origin import ForecastOrigin
from tsfm_rc.paths import resolve
from tsfm_rc.seeding import derive_seed

log = logging.getLogger(__name__)


class TSFMCache:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, model: str, ticker: str, kind: str) -> Path:
        return self.root / "tsfm" / model / f"{ticker}__{kind}.parquet"

    def load(self, model: str, ticker: str, kind: str) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        p = self._path(model, ticker, kind)
        if not p.exists():
            return {}
        df = pd.read_parquet(p)
        out = {}
        for key, med, dec, s in zip(df["key"], df["median"], df["deciles"], df["steps"], strict=True):
            out[key] = (np.asarray(med, dtype=float), np.asarray(dec, dtype=float).reshape(int(s), len(DECILES)))
        return out

    def append(self, model: str, ticker: str, kind: str, rows: list[dict]) -> None:
        if not rows:
            return
        p = self._path(model, ticker, kind)
        p.parent.mkdir(parents=True, exist_ok=True)
        new = pd.DataFrame(rows)
        if p.exists():
            new = pd.concat([pd.read_parquet(p), new], ignore_index=True).drop_duplicates("key", keep="first")
        new.to_parquet(p, index=False)


def cache_key(backend: TSFMBackend, ticker: str, kind: str, origin: pd.Timestamp, steps: int, ctx: np.ndarray) -> str:
    i = backend.info
    return sha256_json(
        {
            "model": i.name, "hf_id": i.hf_id, "revision": i.resolved_revision,
            "package": i.package, "package_version": i.package_version,
            "ticker": ticker, "kind": kind, "origin": str(pd.Timestamp(origin).date()),
            "steps": int(steps), "context_length": int(len(ctx)), "context_sha256": sha256_array(np.asarray(ctx, dtype=np.float64)),
        }
    )


def _requests(daily: dict[str, pd.DataFrame], origins: Sequence[ForecastOrigin], cfg: RunConfig, n_ctx: int):
    """All (ticker, kind, origin, asset_date, context) forecast requests, same skip rules as the engine."""
    for ticker, d in daily.items():
        for kind in cfg.targets.kinds:
            for o in origins:
                hist = o.history(d)
                if len(hist) < cfg.evaluation.min_train_obs:
                    continue
                asset_date = hist.index[-1]
                if (o.timestamp - asset_date).days > MAX_STALENESS_DAYS:
                    continue
                yield ticker, kind, o, asset_date, make_context(hist, kind, n_ctx)


def forecast_with_backend(
    backend: TSFMBackend,
    spec: TSFMSpec,
    daily: dict[str, pd.DataFrame],
    origins: Sequence[ForecastOrigin],
    cfg: RunConfig,
    cache: TSFMCache | None,
) -> pd.DataFrame:
    horizons = cfg.targets.horizons
    steps = max(horizons)
    n_ctx = backend.context_length(cfg.models.context_length, steps)
    reqs = list(_requests(daily, origins, cfg, n_ctx))
    keys = [cache_key(backend, t, k, o.timestamp, steps, c) for t, k, o, _, c in reqs]
    stored: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    if cache is not None:
        for t, k in {(r[0], r[1]) for r in reqs}:
            stored.update(cache.load(spec.name, t, k))
    todo = [i for i, key in enumerate(keys) if key not in stored]
    log.info("%s: %d requests, %d cached, %d to compute", spec.name, len(reqs), len(reqs) - len(todo), len(todo))
    new_rows: dict[tuple[str, str], list[dict]] = {}
    t0 = time.time()
    for b, start in enumerate(range(0, len(todo), spec.batch_size)):
        idx = todo[start : start + spec.batch_size]
        med, dec = backend.predict_batch([reqs[i][4] for i in idx], steps, seed=derive_seed(cfg.seed, spec.name, b))
        for j, i in enumerate(idx):
            t, k, o, _, c = reqs[i]
            stored[keys[i]] = (med[j], dec[j])
            new_rows.setdefault((t, k), []).append(
                {"key": keys[i], "origin": o.timestamp, "steps": steps, "context_length": len(c),
                 "revision": backend.info.resolved_revision, "median": med[j].tolist(), "deciles": dec[j].ravel().tolist()}
            )
    if cache is not None:
        for (t, k), rows in new_rows.items():
            cache.append(spec.name, t, k, rows)
    if todo:
        log.info("%s: computed %d forecasts in %.0fs", spec.name, len(todo), time.time() - t0)

    targets = {(t, k, h): make_target(daily[t], k, h) for t in daily for k in cfg.targets.kinds for h in horizons}
    out = []
    for (t, k, o, asset_date, c), key in zip(reqs, keys, strict=True):
        med, dec = stored[key]
        pts, q1 = to_target_scale(k, med, dec, horizons)
        for h in horizons:
            row = {
                "ticker": t, "target": k, "model": spec.name, "window": "expanding",
                "origin": o.timestamp, "asset_date": asset_date, "ordinal": o.ordinal, "horizon": h,
                "label_end": label_end_date(daily[t].index, asset_date, h),
                "y_true": float(targets[(t, k, h)].get(asset_date, np.nan)), "y_pred": pts[h],
                "n_train": len(c), "refit": False, "flag": "",
            }
            for lv, v in zip(DECILES, q1 if h == 1 else [np.nan] * len(DECILES), strict=True):
                row[qcol(lv)] = float(v)
            out.append(row)
    df = pd.DataFrame(out)
    if len(df) and "rolling" in cfg.evaluation.windows:
        # TSFMs have no training window: the same forecast serves both window variants
        df = pd.concat([df, df.assign(window="rolling")], ignore_index=True)
    return df


def load_backends(cfg: RunConfig) -> tuple[dict[str, TSFMBackend], dict[str, dict]]:
    """Load every enabled TSFM once. Returns (backends by name, status by name)."""
    backends: dict[str, TSFMBackend] = {}
    status: dict[str, dict] = {}
    for spec in cfg.enabled_tsfms():
        try:
            backends[spec.name] = load_backend(spec, cfg.models.context_length, max(cfg.targets.horizons))
            status[spec.name] = {"status": "AVAILABLE", "release_date": str(spec.release_date),
                                 **asdict(backends[spec.name].info)}
        except TSFMUnavailable as e:
            log.warning("%s UNAVAILABLE: %s", spec.name, e)
            status[spec.name] = {"status": "UNAVAILABLE", "reason": str(e), "hf_id": spec.hf_id,
                                 "release_date": str(spec.release_date)}
    return backends, status


def run_tsfms(
    daily: dict[str, pd.DataFrame],
    calendar: pd.DatetimeIndex,
    cfg: RunConfig,
    *,
    use_cache: bool = True,
    loaded: tuple[dict[str, TSFMBackend], dict[str, dict]] | None = None,
) -> tuple[pd.DataFrame, dict[str, dict]]:
    """Forecast with every enabled TSFM. Returns (forecasts, status per model).

    ``loaded`` lets a caller reuse backends (and UNAVAILABLE verdicts) across panels.
    """
    origins = build_origins(calendar, cfg)
    cache = TSFMCache(resolve(cfg.cache_dir)) if use_cache else None
    backends, status = loaded if loaded is not None else load_backends(cfg)
    status = {k: dict(v) for k, v in status.items()}
    parts = []
    specs = {s.name: s for s in cfg.enabled_tsfms()}
    for name, backend in backends.items():
        t0 = time.time()
        parts.append(forecast_with_backend(backend, specs[name], daily, origins, cfg, cache))
        status[name]["seconds"] = round(time.time() - t0, 1)
    fc = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    return fc, status


def run_tsfms_primary(
    daily: dict[str, pd.DataFrame],
    calendar: pd.DatetimeIndex,
    cfg: RunConfig,
    loaded: tuple[dict[str, TSFMBackend], dict[str, dict]],
    *,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Primary pass (amendment A4): each available TSFM at stride-``primary_stride`` origins
    from its own clean-window start (effective release + buffer), expanding window only.

    Origins shared with the main (stride-5) pass hit the output cache, so only the extra
    in-window origins cost inference. Timing per model is written into ``status``.
    """
    from tsfm_rc.contamination.windows import windows_for_models

    backends, status = loaded
    windows = windows_for_models(cfg, status)
    cache = TSFMCache(resolve(cfg.cache_dir)) if use_cache else None
    specs = {s.name: s for s in cfg.enabled_tsfms()}
    parts = []
    for name, backend in backends.items():
        t0 = time.time()
        origins = build_primary_origins(calendar, cfg, start=windows[name].clean_start)
        fc = forecast_with_backend(backend, specs[name], daily, origins, cfg, cache)
        status[name]["primary_pass_seconds"] = round(time.time() - t0, 1)
        status[name]["primary_pass_origins"] = len(origins)
        if len(fc):
            parts.append(fc[fc["window"] == cfg.evaluation.primary_window])
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def write_status(status: dict, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(status, fh, indent=2, default=str)
