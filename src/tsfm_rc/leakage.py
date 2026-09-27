"""Generic look-ahead detectors used throughout the test suite.

The core idea is a *counterfactual future*: if a computation made at origin ``t``
is truly causal, then replacing every observation after ``t`` with garbage must not
change its output at all. ``assert_future_invariant`` performs that experiment.

This is stronger than code review: it catches leaks through any path (feature
construction, scaling, model fitting, hyper-parameter selection, caching) as long
as the future rows are reachable from the arguments passed to the function.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from tsfm_rc.origin import ForecastOrigin


def perturb_future(
    data: pd.DataFrame | pd.Series,
    t: pd.Timestamp,
    seed: int = 0,
    mode: str = "scramble",
) -> pd.DataFrame | pd.Series:
    """Return a copy of ``data`` where all rows strictly after ``t`` are altered.

    Modes
    -----
    ``scramble``: multiply numeric values by random factors in [0.5, 2] and add
        noise. Values stay finite and positive columns stay positive, so leaky code
        runs normally but produces different numbers.
    ``shock``: multiply numeric values by 1000 (large, obvious change).
    """
    rng = np.random.default_rng(seed)
    out = data.copy()
    mask = out.index > pd.Timestamp(t)
    if not mask.any():
        return out
    if isinstance(out, pd.Series):
        frame = out.to_frame()
    else:
        frame = out
    num_cols = [c for c in frame.columns if pd.api.types.is_numeric_dtype(frame[c])]
    for c in num_cols:
        vals = frame.loc[mask, c].to_numpy(dtype=float, copy=True)
        if mode == "scramble":
            factor = rng.uniform(0.5, 2.0, size=vals.shape)
            noise = rng.normal(0.0, 1.0, size=vals.shape) * (np.nanstd(vals) + 1e-3)
            new = vals * factor + np.where(vals > 0, np.abs(noise), noise)
        elif mode == "shock":
            new = vals * 1000.0 + 1.0
        else:
            raise ValueError(f"unknown mode {mode}")
        frame[c] = frame[c].astype(float)
        frame.loc[mask, c] = new
    if isinstance(out, pd.Series):
        return frame.iloc[:, 0].rename(out.name)
    return frame


def _to_array(x: Any) -> np.ndarray:
    if isinstance(x, pd.DataFrame | pd.Series):
        return x.to_numpy(dtype=float)
    if isinstance(x, dict):
        return np.concatenate([_to_array(x[k]).ravel() for k in sorted(x)])
    if hasattr(x, "as_array"):
        return np.asarray(x.as_array(), dtype=float)
    return np.asarray(x, dtype=float)


def assert_future_invariant(
    fn: Callable[[pd.DataFrame | pd.Series, ForecastOrigin], Any],
    data: pd.DataFrame | pd.Series,
    origin: ForecastOrigin,
    *,
    seeds: tuple[int, ...] = (1, 2),
    modes: tuple[str, ...] = ("scramble", "shock"),
    atol: float = 0.0,
) -> None:
    """Assert ``fn(data, origin)`` is unchanged when data after the origin is perturbed.

    ``fn`` receives the FULL data (as the engine's panel would be) plus the origin,
    and is responsible for slicing through ``origin.history``. A correct function
    therefore never sees the perturbed rows. ``atol=0`` demands bit-identical output.
    """
    baseline = _to_array(fn(data, origin))
    for mode in modes:
        for seed in seeds:
            perturbed = perturb_future(data, origin.timestamp, seed=seed, mode=mode)
            got = _to_array(fn(perturbed, origin))
            if baseline.shape != got.shape or not np.allclose(
                baseline, got, atol=atol, rtol=0.0, equal_nan=True
            ):
                diff = np.nanmax(np.abs(baseline - got)) if baseline.shape == got.shape else "shape"
                raise AssertionError(
                    f"Look-ahead detected at origin {origin.timestamp.date()} "
                    f"(mode={mode}, seed={seed}, max abs diff={diff})"
                )


def is_future_invariant(*args: Any, **kwargs: Any) -> bool:
    """Boolean version of :func:`assert_future_invariant` (used for negative controls)."""
    try:
        assert_future_invariant(*args, **kwargs)
    except AssertionError:
        return False
    return True
