"""Clean vs possibly-seen evaluation windows per TSFM (PREREGISTRATION.md s.9, amendment A1).

effective release  = max(documented release date, last commit date of the weight files)
possibly seen      = origin >= test_start and the label window ends before effective release
clean              = origin >= effective release + buffer (30 days)
gap                = everything in between (excluded from both)

Labels are assigned per (asset, origin, horizon) row using ``label_end``, the last trading
day of the target window, so no target period straddles the boundary.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

from tsfm_rc.config import RunConfig


@dataclass(frozen=True)
class ContaminationWindows:
    model: str
    release_date: pd.Timestamp
    weights_date: pd.Timestamp | None
    effective_release: pd.Timestamp
    clean_start: pd.Timestamp
    test_start: pd.Timestamp

    def label(self, origin: pd.Series, label_end: pd.Series) -> pd.Series:
        origin = pd.to_datetime(origin)
        label_end = pd.to_datetime(label_end)
        out = np.full(len(origin), "gap", dtype=object)
        seen = (origin >= self.test_start) & label_end.notna() & (label_end < self.effective_release)
        clean = origin >= self.clean_start
        out[seen.to_numpy()] = "seen"
        out[clean.to_numpy()] = "clean"
        out[(origin < self.test_start).to_numpy()] = "pre_test"
        return pd.Series(out, index=origin.index, name="window_label")

    def as_dict(self) -> dict:
        return {k: (str(v.date()) if isinstance(v, pd.Timestamp) else v) for k, v in self.__dict__.items()}


def windows_for_models(cfg: RunConfig, status: dict[str, dict] | None = None) -> dict[str, ContaminationWindows]:
    """Windows for every *configured* TSFM (available or not), using weight dates when known."""
    status = status or {}
    buffer = pd.Timedelta(days=cfg.contamination.buffer_days)
    test_start = pd.Timestamp(cfg.evaluation.test_start)
    out = {}
    for spec in cfg.models.tsfms:
        rel = pd.Timestamp(spec.release_date)
        wd_raw = status.get(spec.name, {}).get("weights_commit_date")
        wd = pd.Timestamp(wd_raw) if wd_raw else None
        eff = max(rel, wd) if wd is not None else rel
        out[spec.name] = ContaminationWindows(spec.name, rel, wd, eff, eff + buffer, test_start)
    return out


def common_clean_start(windows: dict[str, ContaminationWindows], available: list[str] | None = None) -> pd.Timestamp | None:
    """Start of the window that is clean for every evaluated TSFM.

    Uses the available models if any, otherwise all configured ones (so baseline-only
    results are still reported on the same, pre-registered window).
    """
    names = [m for m in (available or []) if m in windows] or list(windows)
    if not names:
        return None
    return max(windows[m].clean_start for m in names)


def today() -> dt.date:  # pragma: no cover - trivial, separated for tests
    return dt.date.today()
