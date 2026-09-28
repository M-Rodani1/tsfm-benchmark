"""Stored results for the lessons, identical on your machine and on the website.

The lessons read the study's stored statistics tables. Two places hold the same numbers:

- ``results/<run>/stats/<table>.parquet``: written by the pipeline (``make smoke``);
- ``site/public/data/results/<run>/<version>/tables/<table>.json``: exported from those
  Parquet files by ``make publish-results`` (tests/test_publish.py checks they are equal).

On your machine the Parquet file is used when it exists. In the browser (Pyodide: no
``pyarrow``, no ``results/`` folder) the website mounts the published JSON at the same
relative path under ``TSFM_RC_ROOT``, and the JSON is used. No statistic is ever recomputed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tsfm_rc.paths import RESULTS_DIR, ROOT

PUBLISHED_DIR = ROOT / "site" / "public" / "data" / "results"


def published_index() -> dict:
    p = PUBLISHED_DIR / "index.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"runs": []}


def _published_entry(run: str) -> dict:
    for r in published_index().get("runs", []):
        if r["run"] == run:
            return r
    raise FileNotFoundError(f"run '{run}' is neither in results/ nor published in {PUBLISHED_DIR} (run `make smoke`)")


def _parquet_available() -> bool:
    try:
        import pyarrow  # noqa: F401
    except ImportError:
        return False
    return True


def stats_table(run: str, table: str) -> pd.DataFrame:
    """One stored statistics table, e.g. ``stats_table("smoke", "dm_all")``."""
    pq = RESULTS_DIR / run / "stats" / f"{table}.parquet"
    if pq.exists() and _parquet_available():
        return pd.read_parquet(pq)
    entry = _published_entry(run)
    rel = entry["tables"].get(table)
    if rel is None:
        raise FileNotFoundError(f"table '{table}' is not published for run '{run}'")
    return pd.read_json(PUBLISHED_DIR / rel, orient="table", precise_float=True)


def report_text(run: str) -> str:
    """The run's generated report (``reports/<run>/RESULTS.md``), or its published copy."""
    local = ROOT / "reports" / run / "RESULTS.md"
    if local.exists():
        return local.read_text(encoding="utf-8")
    entry = _published_entry(run)
    return Path(PUBLISHED_DIR / entry["report"]).read_text(encoding="utf-8")
