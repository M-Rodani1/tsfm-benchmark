"""Seeding utilities.

Two ideas:

1. ``seed_everything`` seeds the global RNGs (``random``, NumPy, PyTorch if installed).
2. ``derive_seed`` gives every independent task (e.g. "GARCH on SPY, origin 2019-03-01")
   its own seed computed from the run seed and a tuple of keys. Results therefore do
   not depend on the order in which tasks run or on how many worker processes are used.
"""

from __future__ import annotations

import hashlib
import os
import random

import numpy as np


def derive_seed(base_seed: int, *keys: object) -> int:
    """Deterministically derive a 32-bit seed from a base seed and arbitrary keys."""
    payload = "|".join([str(base_seed), *[str(k) for k in keys]]).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "little")


def rng(base_seed: int, *keys: object) -> np.random.Generator:
    """A NumPy Generator seeded from ``derive_seed(base_seed, *keys)``."""
    return np.random.default_rng(derive_seed(base_seed, *keys))


def seed_everything(seed: int) -> None:
    """Seed Python, NumPy and (if available) PyTorch global RNGs."""
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed % (2**32))
    try:  # torch is optional (only with the `tsfm` extra)
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():  # pragma: no cover - no GPU in CI
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass
