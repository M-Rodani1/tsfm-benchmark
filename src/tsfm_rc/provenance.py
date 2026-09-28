"""Provenance: everything needed to trace a stored number back to its origin.

A provenance record contains the config hash, the data hash(es), the exact versions
of every numerically relevant package, the git commit (and whether the working
tree was dirty), Python/platform info and a UTC timestamp. It is written as JSON
next to every results folder and embedded (as a JSON string) in Parquet metadata.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

import pandas as pd

from tsfm_rc.paths import ROOT

TRACKED_PACKAGES = (
    "tsfm-reality-check",
    "numpy",
    "pandas",
    "scipy",
    "statsmodels",
    "arch",
    "lightgbm",
    "pyarrow",
    "matplotlib",
    "pydantic",
    "yfinance",
    "torch",
    "transformers",
    "chronos-forecasting",
    "timesfm",
    "uni2ts",
    "gluonts",
    "huggingface-hub",
)


def package_versions(packages: tuple[str, ...] = TRACKED_PACKAGES) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in packages:
        try:
            out[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            out[p] = "not-installed"
    return out


def git_info(root: Path = ROOT) -> dict[str, Any]:
    def _run(*args: str) -> str | None:
        try:
            return subprocess.run(
                ["git", *args], cwd=root, capture_output=True, text=True, check=True, timeout=10
            ).stdout.strip()
        except Exception:
            return None

    commit = _run("rev-parse", "HEAD")
    # "dirty" = tracked code/config/data differ from the commit. Generated outputs
    # (results/, reports/) are excluded: a run rewrites them, so counting them would
    # make every run look dirty and hide real code changes.
    status = _run("status", "--porcelain", "--untracked-files=no", "--", ".", ":(exclude)results", ":(exclude)reports")
    return {
        "commit": commit or "unknown",
        "dirty": bool(status) if status is not None else None,
        "branch": _run("rev-parse", "--abbrev-ref", "HEAD") or "unknown",
    }


def provenance_record(
    *,
    config_hash: str,
    data_hash: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "config_hash": config_hash,
        "data_hash": data_hash,
        "git": git_info(),
        "packages": package_versions(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        # OpenBLAS kernel family (pinned by the CLI on x86-64, DECISIONS D-054); "auto" = chosen by the CPU
        "openblas_coretype": os.environ.get("OPENBLAS_CORETYPE") or "auto",
        "created_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "argv": sys.argv,
    }
    if extra:
        rec.update(extra)
    return rec


def write_parquet_with_provenance(df: pd.DataFrame, path: str | Path, prov: dict[str, Any]) -> None:
    """Write ``df`` to Parquet and embed ``prov`` in the file's key-value metadata.

    The provenance JSON is stored under the key ``tsfm_rc_provenance``. It can be
    read back with :func:`read_parquet_provenance`.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    meta = dict(table.schema.metadata or {})
    meta[b"tsfm_rc_provenance"] = json.dumps(prov, sort_keys=True, default=str).encode()
    table = table.replace_schema_metadata(meta)
    pq.write_table(table, path)


def read_parquet_provenance(path: str | Path) -> dict[str, Any]:
    import pyarrow.parquet as pq

    meta = pq.read_schema(path).metadata or {}
    raw = meta.get(b"tsfm_rc_provenance")
    return json.loads(raw) if raw else {}
