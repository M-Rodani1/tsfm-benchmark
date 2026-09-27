"""Build forecasters from names in the config."""

from __future__ import annotations

from tsfm_rc.config import RunConfig
from tsfm_rc.models.base import Forecaster
from tsfm_rc.models.baselines import ARBIC, BASELINE_CLASSES, EWMA, HAR, LGBM


def make_baseline(name: str, kind: str, cfg: RunConfig, seed: int) -> Forecaster:
    if name not in BASELINE_CLASSES:
        raise KeyError(f"unknown baseline '{name}'")
    cls = BASELINE_CLASSES[name]
    horizons = cfg.targets.horizons
    if cls is ARBIC:
        return ARBIC(kind, seed, pmax=cfg.models.ar_max_lag)
    if cls is EWMA:
        return EWMA(kind, seed, lam=cfg.models.ewma_lambda)
    if cls is HAR:
        return HAR(kind, seed, horizons=horizons)
    if cls is LGBM:
        return LGBM(kind, seed, horizons=horizons, params=cfg.models.lgbm.model_dump())
    return cls(kind, seed)


def refit_every(name: str, cfg: RunConfig) -> int:
    return int(cfg.models.refit_every.get(name, 1))
