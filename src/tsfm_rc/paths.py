"""Canonical repository paths. Everything is resolved relative to the repo root."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    """Return the repository root.

    ``TSFM_RC_ROOT`` overrides the default (useful when the package is installed
    elsewhere). Otherwise we walk up from this file until we find ``pyproject.toml``.
    """
    env = os.environ.get("TSFM_RC_ROOT")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd().resolve()


ROOT = repo_root()
CONFIG_DIR = ROOT / "configs"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
FIXTURE_DIR = DATA_DIR / "fixtures"
CACHE_DIR = ROOT / "cache"
RESULTS_DIR = ROOT / "results"
REPORTS_DIR = ROOT / "reports"
DOCS_DIR = ROOT / "docs"
LESSONS_DIR = ROOT / "lessons"


def resolve(path: str | Path) -> Path:
    """Resolve a (possibly relative) path against the repo root."""
    p = Path(path)
    return p if p.is_absolute() else (ROOT / p)
