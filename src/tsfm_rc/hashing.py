"""Deterministic hashing helpers (SHA-256) for files, arrays, frames and configs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(obj: Any) -> str:
    """JSON with sorted keys and no whitespace, so equal objects hash equally."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256_json(obj: Any) -> str:
    return sha256_bytes(canonical_json(obj).encode("utf-8"))


def sha256_array(arr: np.ndarray) -> str:
    """Hash of an array's dtype, shape and raw bytes (C order)."""
    a = np.ascontiguousarray(arr)
    h = hashlib.sha256()
    h.update(str(a.dtype).encode())
    h.update(str(a.shape).encode())
    h.update(a.tobytes())
    return h.hexdigest()


def sha256_frame(df: pd.DataFrame | pd.Series) -> str:
    """Hash of a DataFrame/Series content including index and column names.

    Uses ``pd.util.hash_pandas_object`` (stable across platforms for the same
    pandas version) plus the column names and dtypes.
    """
    h = hashlib.sha256()
    if isinstance(df, pd.Series):
        df = df.to_frame(name=str(df.name))
    h.update(canonical_json([str(c) for c in df.columns]).encode())
    h.update(canonical_json([str(t) for t in df.dtypes]).encode())
    h.update(pd.util.hash_pandas_object(df, index=True).values.tobytes())
    return h.hexdigest()
