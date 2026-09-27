"""Daily series and h-step forecast targets (PREREGISTRATION.md section 3).

Daily series (one row per trading day of the asset):

- ``r``       100 * ln(adj_close_t / adj_close_{t-1})              percent log return
- ``gk``      Garman-Klass variance in %^2 (NaN when high == low)
- ``logvol``  ln(volume)  (NaN when volume is missing)

Model inputs (causal forward-fill of the rare missing values, never used as targets):

- ``log_gk_in``  ln(gk) forward-filled
- ``logvol_in``  logvol forward-filled

h-step targets for an origin at row i use rows i+1, ..., i+h of the asset's own index:

- returns: sum of r;   rv: mean of gk;   volume: mean of logvol.
A target is NaN if any of its h inputs is missing or the window runs past the data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

GK_CONST = 2.0 * np.log(2.0) - 1.0  # 0.386294...

# target kind -> (daily column, aggregation)
TARGET_SPEC: dict[str, tuple[str, str]] = {
    "returns": ("r", "sum"),
    "rv": ("gk", "mean"),
    "volume": ("logvol", "mean"),
}
# target kind -> column fed to TSFMs / used as the "daily target series" by baselines
INPUT_COL: dict[str, str] = {"returns": "r", "rv": "log_gk_in", "volume": "logvol_in"}


def log_returns_pct(adj_close: pd.Series) -> pd.Series:
    """Percent log returns: 100 ln(P_t / P_{t-1}). First value is NaN."""
    return (100.0 * np.log(adj_close.astype(float))).diff().rename("r")


def garman_klass_variance(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Garman & Klass (1980) daily variance estimator, in %^2.

    sigma^2 = 0.5 [ln(H/L)]^2 - (2 ln 2 - 1) [ln(C/O)]^2, times 100^2.

    Non-negative whenever L <= O, C <= H because |ln(C/O)| <= ln(H/L) and
    0.5 > 2 ln 2 - 1. Returns NaN when H == L (zero range; treated as missing).
    """
    hl = np.log(high.astype(float) / low.astype(float))
    co = np.log(close.astype(float) / open_.astype(float))
    gk = 1e4 * (0.5 * hl**2 - GK_CONST * co**2)
    gk = gk.where(hl > 0)
    return gk.rename("gk")


def parkinson_variance(high: pd.Series, low: pd.Series) -> pd.Series:
    """Parkinson (1980) estimator in %^2: [ln(H/L)]^2 / (4 ln 2). Used for comparison only."""
    hl = np.log(high.astype(float) / low.astype(float))
    return (1e4 * hl**2 / (4.0 * np.log(2.0))).where(hl > 0).rename("parkinson")


def daily_series(clean: pd.DataFrame) -> pd.DataFrame:
    """Build the per-asset daily frame from a cleaned OHLCV frame."""
    out = pd.DataFrame(index=clean.index)
    out["r"] = log_returns_pct(clean["adj_close"])
    out["gk"] = garman_klass_variance(clean["open"], clean["high"], clean["low"], clean["close"])
    out["logvol"] = np.log(clean["volume"].astype(float)).where(clean["volume"] > 0)
    out["log_gk_in"] = np.log(out["gk"]).ffill()
    out["logvol_in"] = out["logvol"].ffill()
    out["dow"] = out.index.dayofweek.astype(int)
    return out


def horizon_target(daily_values: pd.Series, h: int, how: str) -> pd.Series:
    """Aggregate rows i+1..i+h into a value indexed at row i (the origin).

    Uses a trailing window of length h ending at row i+h, shifted back by h rows.
    ``min_periods=h`` makes the result NaN if any input is NaN.
    """
    if h < 1:
        raise ValueError("h must be >= 1")
    roll = daily_values.rolling(h, min_periods=h)
    agg = roll.sum() if how == "sum" else roll.mean() if how == "mean" else None
    if agg is None:
        raise ValueError(f"unknown aggregation {how}")
    return agg.shift(-h)


def make_target(daily: pd.DataFrame, kind: str, h: int) -> pd.Series:
    col, how = TARGET_SPEC[kind]
    return horizon_target(daily[col], h, how).rename(f"{kind}_h{h}")


def aggregate_path(path: np.ndarray, kind: str, h: int) -> np.ndarray:
    """Aggregate per-step forecasts (..., steps) to the h-step target of ``kind``.

    ``path`` holds per-step forecasts on the *target* scale (returns in %, variance in
    %^2, log volume). Used for TSFM paths and iterated baselines.
    """
    p = np.asarray(path, dtype=float)[..., :h]
    if p.shape[-1] < h:
        raise ValueError(f"path has {p.shape[-1]} steps, need {h}")
    return p.sum(axis=-1) if TARGET_SPEC[kind][1] == "sum" else p.mean(axis=-1)
