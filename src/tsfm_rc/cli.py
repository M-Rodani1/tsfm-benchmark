"""Command-line entry point: ``tsfm-rc <command> [options]``.

Commands are added build by build; ``tsfm-rc --help`` lists what exists.
"""

from __future__ import annotations

import argparse
import logging
import sys

from tsfm_rc.config import config_hash, load_config
from tsfm_rc.logging_utils import setup_logging

log = logging.getLogger("tsfm_rc.cli")


def _cmd_validate(args: argparse.Namespace) -> int:
    for path in args.configs:
        cfg = load_config(path)
        print(f"{path}: OK  name={cfg.name}  config_hash={config_hash(cfg)[:16]}")
    return 0


def _cmd_all(args: argparse.Namespace) -> int:
    """Run every pipeline stage implemented so far for one config."""
    cfg = load_config(args.config)
    print(f"[validate] {args.config}: OK (config_hash={config_hash(cfg)[:16]})")
    # Later builds append stages here (fetch/load data, forecast, evaluate, report, dashboard).
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tsfm-rc", description="TSFM Reality Check")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="validate one or more YAML configs")
    v.add_argument("configs", nargs="+")
    v.set_defaults(func=_cmd_validate)

    a = sub.add_parser("all", help="run every implemented stage for a config")
    a.add_argument("config")
    a.add_argument("--fetch", action="store_true", help="download missing raw data first")
    a.set_defaults(func=_cmd_all)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(logging.DEBUG if args.verbose else logging.INFO)
    return int(args.func(args) or 0)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
