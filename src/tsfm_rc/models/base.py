"""The Forecaster interface shared by baselines and foundation models.

    fit(history)                    -> None   (estimate parameters; no-op for zero-shot TSFMs)
    predict(history, horizons)      -> Forecast (point forecast per horizon [+ quantiles])

``history`` is always the per-asset daily frame cut at the forecast origin by
:meth:`tsfm_rc.origin.ForecastOrigin.history` (columns: r, gk, logvol, log_gk_in,
logvol_in, dow). A forecaster never receives data after the origin, and every
forecaster in the registry is checked by a future-perturbation test.

Forecasts are always on the *target* scale of section 3 of the pre-registration:
returns -> sum of percent log returns over h; rv -> mean daily GK variance (%^2);
volume -> mean log volume.
"""

from __future__ import annotations

import abc
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from tsfm_rc.data.targets import make_target


@dataclass(frozen=True)
class PointForecast:
    values: dict[int, float]  # horizon -> point forecast

    def __getitem__(self, h: int) -> float:
        return self.values[h]


@dataclass(frozen=True)
class QuantileForecast:
    levels: tuple[float, ...]
    values: dict[int, np.ndarray]  # horizon -> array of len(levels), non-decreasing

    def __post_init__(self) -> None:
        for h, v in self.values.items():
            v = np.asarray(v, dtype=float)
            if v.shape != (len(self.levels),):
                raise ValueError(f"h={h}: expected {len(self.levels)} quantiles, got {v.shape}")
            # enforce monotonicity (quantile crossing can occur in some models)
            self.values[h] = np.maximum.accumulate(v)


@dataclass
class Forecast:
    point: PointForecast
    quantiles: QuantileForecast | None = None
    meta: dict = field(default_factory=dict)

    def as_array(self) -> np.ndarray:
        """Flat array of all numbers (used by leakage tests)."""
        parts = [np.array([self.point.values[h] for h in sorted(self.point.values)], dtype=float)]
        if self.quantiles is not None:
            parts += [np.asarray(self.quantiles.values[h]) for h in sorted(self.quantiles.values)]
        return np.concatenate(parts)


class Forecaster(abc.ABC):
    """Base class. Subclasses set ``name`` and ``kinds`` and implement fit/predict."""

    name: str = "abstract"
    kinds: tuple[str, ...] = ()
    is_tsfm: bool = False

    def __init__(self, kind: str, seed: int = 0):
        if kind not in self.kinds:
            raise ValueError(f"{self.name} does not support target '{kind}'")
        self.kind = kind
        self.seed = seed
        self.fitted = False

    @abc.abstractmethod
    def fit(self, history: pd.DataFrame) -> None: ...

    @abc.abstractmethod
    def predict(
        self,
        history: pd.DataFrame,
        horizons: Sequence[int],
        quantile_levels: Sequence[float] | None = None,
    ) -> Forecast: ...

    def __repr__(self) -> str:
        return f"{type(self).__name__}(kind={self.kind!r})"


# ------------------------------------------------------------------ helpers


def daily_target_series(history: pd.DataFrame, kind: str) -> pd.Series:
    """The daily series whose h-step aggregate is the target (inputs forward-filled)."""
    if kind == "returns":
        return history["r"]
    if kind == "rv":
        return np.exp(history["log_gk_in"])  # GK level with rare gaps forward-filled
    if kind == "volume":
        return history["logvol_in"]
    raise ValueError(kind)


def training_labels(history: pd.DataFrame, kind: str, h: int) -> pd.Series:
    """h-step labels computed *inside* the history.

    Because ``history`` ends at the origin, any label whose window would extend past
    the origin is NaN here and is therefore dropped: the label-availability rule of
    :meth:`ForecastOrigin.label_available_mask` holds by construction.
    """
    y = make_target(history, kind, h)
    last_ok = len(history) - 1 - h
    if y.notna().any():
        assert np.flatnonzero(y.notna().to_numpy())[-1] <= last_ok, "label leak: unrealised label"
    return y


def ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta
