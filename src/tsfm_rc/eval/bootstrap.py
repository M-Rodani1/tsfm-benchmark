"""Stationary bootstrap (Politis & Romano 1994) and the pre-registered block-length rule."""

from __future__ import annotations

import math

import numpy as np


def block_length(T: int, h_eff: int = 1) -> int:
    """Pre-registered expected block length: max(ceil(T^(1/3)), 2 h_eff) (DECISIONS D-017)."""
    return int(max(math.ceil(T ** (1.0 / 3.0)), 2 * max(1, h_eff)))


def stationary_bootstrap_indices(T: int, B: int, block: float, rng: np.random.Generator) -> np.ndarray:
    """(B, T) matrix of resampling indices.

    Each index starts a new block with probability p = 1/block (geometric block lengths
    with mean ``block``), otherwise continues the previous index + 1, wrapping around
    circularly. ``block = 1`` is the i.i.d. bootstrap.
    """
    if T < 1 or B < 1:
        raise ValueError("T and B must be positive")
    p = 1.0 / max(block, 1.0)
    idx = np.empty((B, T), dtype=np.int64)
    idx[:, 0] = rng.integers(0, T, size=B)
    new_start = rng.random((B, T)) < p
    fresh = rng.integers(0, T, size=(B, T))
    for t in range(1, T):
        idx[:, t] = np.where(new_start[:, t], fresh[:, t], (idx[:, t - 1] + 1) % T)
    return idx
