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


def refit_every(name: str, cfg: RunConfig, stride: int | None = None) -> int:
    """Re-fit interval in origins for a pass sampled every ``stride`` trading days.

    ``models.refit_every`` is pre-registered in origins of the main schedule
    (``evaluation.stride``). A pass with another stride (the A4 stride-1 primary pass) keeps
    the same interval in *trading days*: GARCH every 4 origins at stride 5 = every 20 origins
    at stride 1 (DECISIONS D-040). Models without an entry re-fit at every origin in any pass.
    """
    base = cfg.models.refit_every.get(name)
    if base is None:
        return 1
    if stride is None or stride == cfg.evaluation.stride:
        return int(base)
    return max(1, int(round(base * cfg.evaluation.stride / stride)))
