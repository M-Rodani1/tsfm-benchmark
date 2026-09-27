"""Logging setup: one consistent format, optional log file per run."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int | str = logging.INFO, log_file: str | Path | None = None) -> None:
    """Configure the root logger. Safe to call more than once."""
    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)
    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(logging.Formatter(FORMAT, DATEFMT))
    root.addHandler(stream)
    if log_file is not None:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        fh.setFormatter(logging.Formatter(FORMAT, DATEFMT))
        root.addHandler(fh)
    # Quieten chatty third-party libraries.
    for noisy in ("matplotlib", "urllib3", "yfinance", "peewee", "PIL", "numexpr"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
