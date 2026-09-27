"""The ForecastOrigin abstraction: the single place where data is cut at time t.

Rule (docs/PREREGISTRATION.md, section 3): a forecast made at origin ``t`` may use
only rows whose timestamp is ``<= t``. Every model, feature builder, scaler and
hyper-parameter choice in this repository receives its data through
:meth:`ForecastOrigin.history`, which physically removes later rows. The tests in
``tests/test_origin.py`` and ``tests/test_leakage_*.py`` check this by perturbing
all data after ``t`` and asserting that forecasts do not change.

A second, subtler leak affects *direct* multi-step regressions (HAR, LightGBM):
a training pair ``(x_s, y_{s,h})`` is only usable at origin ``t`` if its label
window ``(s, s+h]`` has already been observed, i.e. ``pos(s) + h <= pos(t)``.
:meth:`ForecastOrigin.label_available_mask` implements that rule.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd


class LeakageError(RuntimeError):
    """Raised when data from after a forecast origin reaches a forecaster."""


@dataclass(frozen=True, order=True)
class ForecastOrigin:
    """A forecast origin.

    Attributes
    ----------
    timestamp:
        The last timestamp whose data may be used (inclusive). Forecasts target
        the trading days strictly after it.
    ordinal:
        Position of this origin in its schedule (0, 1, 2, ...). Used by re-fit
        schedules ("re-fit every k origins").
    """

    timestamp: pd.Timestamp
    ordinal: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", pd.Timestamp(self.timestamp))

    # ------------------------------------------------------------------ slicing
    def history(self, data: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
        """Return a *copy* of ``data`` restricted to rows with index ``<= timestamp``.

        ``data`` must have a sorted DatetimeIndex. The copy means later in-place
        edits by a model can never write into the shared panel.
        """
        _check_index(data.index)
        out = data.loc[: self.timestamp].copy()
        if len(out) and out.index.max() > self.timestamp:  # pragma: no cover - defensive
            raise LeakageError("slice contains rows after the origin")
        return out

    def assert_no_future(self, data: pd.DataFrame | pd.Series | pd.DatetimeIndex) -> None:
        """Raise :class:`LeakageError` if ``data`` contains any timestamp after the origin."""
        idx = data if isinstance(data, pd.DatetimeIndex) else data.index
        if len(idx) and idx.max() > self.timestamp:
            raise LeakageError(
                f"data reaches {idx.max().date()} but origin is {self.timestamp.date()}"
            )

    # ------------------------------------------------------------ label logic
    def position_in(self, index: pd.DatetimeIndex) -> int:
        """Integer position of the last index entry ``<= timestamp`` (-1 if none)."""
        _check_index(index)
        return int(index.searchsorted(self.timestamp, side="right")) - 1

    def label_available_mask(self, index: pd.DatetimeIndex, horizon: int) -> np.ndarray:
        """Boolean mask over ``index``: True where the h-step label is fully observed.

        Row ``s`` (position ``i``) has label window ``(i, i + h]`` in the series' own
        trading-day positions. It is observable at this origin iff ``i + h <= pos(t)``.
        """
        if horizon < 1:
            raise ValueError("horizon must be >= 1")
        p = self.position_in(index)
        positions = np.arange(len(index))
        return positions + horizon <= p


def _check_index(index: pd.Index) -> None:
    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError("data must be indexed by a pandas DatetimeIndex")
    if not index.is_monotonic_increasing:
        raise ValueError("DatetimeIndex must be sorted ascending")


def make_origin_schedule(
    calendar: pd.DatetimeIndex | Iterable[pd.Timestamp],
    test_start: pd.Timestamp | str,
    stride: int,
    min_train_obs: int,
    end: pd.Timestamp | str | None = None,
) -> list[ForecastOrigin]:
    """Build the list of forecast origins on a trading calendar.

    - The first origin is the first calendar date ``>= test_start`` that also has at
      least ``min_train_obs`` calendar dates up to and including it.
    - Subsequent origins follow every ``stride`` trading days.
    - Origins after ``end`` (if given) are dropped. Label availability for each
      horizon is handled later, when targets are attached.
    """
    cal = pd.DatetimeIndex(sorted(pd.DatetimeIndex(list(calendar)).unique()))
    if stride < 1:
        raise ValueError("stride must be >= 1")
    start_pos = max(int(cal.searchsorted(pd.Timestamp(test_start), side="left")), min_train_obs - 1)
    if start_pos >= len(cal):
        return []
    positions = range(start_pos, len(cal), stride)
    end_ts = pd.Timestamp(end) if end is not None else None
    origins = []
    for k, pos in enumerate(positions):
        ts = cal[pos]
        if end_ts is not None and ts > end_ts:
            break
        origins.append(ForecastOrigin(ts, k))
    return origins
