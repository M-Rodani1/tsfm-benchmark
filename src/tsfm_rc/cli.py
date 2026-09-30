"""Command-line entry point: ``tsfm-rc <command> [options]``. See ``tsfm-rc --help``."""

from __future__ import annotations

import argparse
import logging
import os
import platform
import sys

# Bit-for-bit reproducibility across x86-64 machines (DECISIONS D-054). The OpenBLAS copies
# bundled with the NumPy and SciPy wheels pick a CPU-specific kernel at load time, and the
# GARCH fits (`arch`) stop at slightly different optima under different kernels. Pin the
# generic Prescott kernels, which produced every committed artifact, unless the caller chose
# a kernel. It only takes effect before NumPy is loaded (nothing above imports it); if NumPy
# is already loaded (this module imported as a library, e.g. by the tests), setting it would
# reach only child processes and make them differ from this one, so it is left alone.
if platform.machine().lower() in ("x86_64", "amd64") and "numpy" not in sys.modules:
    os.environ.setdefault("OPENBLAS_CORETYPE", "Prescott")

from tsfm_rc.config import config_hash, load_config  # noqa: E402
from tsfm_rc.logging_utils import setup_logging  # noqa: E402

log = logging.getLogger("tsfm_rc.cli")


def _cmd_validate(args: argparse.Namespace) -> int:
    for path in args.configs:
        cfg = load_config(path)
        print(f"{path}: OK  name={cfg.name}  config_hash={config_hash(cfg)[:16]}")
    return 0


def _cmd_fixtures(args: argparse.Namespace) -> int:
    from tsfm_rc.data.synthetic import write_fixtures
    from tsfm_rc.paths import FIXTURE_DIR

    man = write_fixtures(FIXTURE_DIR)
    for f, h in man["files"].items():
        print(f"wrote {FIXTURE_DIR / f}  sha256={h}")
    return 0


def _cmd_fetch(args: argparse.Namespace) -> int:
    from tsfm_rc.data.panel import fetch_all

    cfg = load_config(args.config)
    status = fetch_all(cfg)
    failed = [t for t, s in status.items() if s.startswith("FAILED")]
    for t, s in status.items():
        print(f"{t:6s} {s}")
    if failed:
        print(
            f"\n{len(failed)} ticker(s) failed. If every ticker failed, you are probably offline or "
            "Yahoo is blocking requests: try again later, or put Yahoo-format CSVs in a folder and use "
            "`provider: csv` with `csv_dir:` in the config (see docs/DECISIONS.md, D-022)."
        )
    return 1 if failed else 0


def _cmd_run(args: argparse.Namespace) -> int:
    from tsfm_rc.pipeline.run import run_all_stages

    cfg = load_config(args.config)
    print(f"[validate] {args.config}: OK (config_hash={config_hash(cfg)[:16]})")
    return run_all_stages(cfg, allow_fetch=args.fetch)


def _cmd_evaluate(args: argparse.Namespace) -> int:
    from tsfm_rc.pipeline.run import stage_data, stage_evaluate

    cfg = load_config(args.config)
    stage_evaluate(cfg, stage_data(cfg, allow_fetch=False))
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from tsfm_rc.paths import REPORTS_DIR
    from tsfm_rc.reports.results_md import write_index, write_report

    cfg = load_config(args.config)
    if not (cfg.run_dir / "stats").exists():
        print(f"[report] no statistics in {cfg.run_dir}; run `tsfm-rc run {args.config}` first")
        return 1
    path = write_report(cfg, cfg.run_dir, REPORTS_DIR)
    idx = write_index(REPORTS_DIR)
    print(f"[report] {path} (index: {idx})")
    return 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    from tsfm_rc.paths import REPORTS_DIR, RESULTS_DIR
    from tsfm_rc.reports.dashboard import build_dashboard

    path = build_dashboard(RESULTS_DIR, REPORTS_DIR / "dashboard" / "index.html")
    print(f"[dashboard] {path} ({path.stat().st_size / 1e6:.1f} MB, open it in any browser; no server needed)")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    from tsfm_rc.pipeline.doctor import run_doctor

    return run_doctor(online=args.online)


def _cmd_flashcards(args: argparse.Namespace) -> int:
    from tsfm_rc.pipeline.flashcards import main as flash_main

    return flash_main()


def _cmd_publish(args: argparse.Namespace) -> int:
    from tsfm_rc.pipeline.publish import PUBLISH_ROOT, publish

    index = publish(args.runs or None)
    for e in index["runs"]:
        tag = e["label"] or "real data"
        print(f"[publish] {e['run']}: version {e['version']} ({tag}) -> {PUBLISH_ROOT / e['run'] / e['version']}")
    if not index["real_results_available"]:
        print("[publish] no real-data run published yet: the website keeps showing the pending `make reproduce` task.")
    print("[publish] commit site/public/data/results and push; the website rebuilds from it.")
    return 0


def _has_data(cfg) -> bool:
    from tsfm_rc.data.cache import RawCache
    from tsfm_rc.paths import resolve

    if cfg.data.provider == "fixture":
        return True
    cache = RawCache(resolve(cfg.data.raw_dir))
    return all(cache.find(cfg.data.provider, t, cfg.data.start, cfg.data.end) for t in cfg.data.tickers)


def _cmd_all(args: argparse.Namespace) -> int:
    """Forecast, evaluate, then build every report for one config."""
    if getattr(args, "skip_if_no_data", False) and not args.fetch and not _has_data(load_config(args.config)):
        print(f"[all] {args.config}: no cached raw data -> skipped (run `make fetch-data CONFIG={args.config}`)")
        return 0
    rc = _cmd_run(args)
    if rc:
        return rc
    rc = _cmd_report(args)
    if rc:
        return rc
    return _cmd_dashboard(args)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tsfm-rc", description="TSFM Reality Check")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="validate one or more YAML configs")
    v.add_argument("configs", nargs="+")
    v.set_defaults(func=_cmd_validate)

    fx = sub.add_parser("fixtures", help="regenerate the committed synthetic fixtures")
    fx.set_defaults(func=_cmd_fixtures)

    f = sub.add_parser("fetch", help="download raw data for a config into the immutable cache")
    f.add_argument("config")
    f.set_defaults(func=_cmd_fetch)

    for name, fn, hlp in [
        ("run", _cmd_run, "data -> forecasts -> statistics for a config"),
        ("all", _cmd_all, "run + reports + dashboard for a config"),
    ]:
        a = sub.add_parser(name, help=hlp)
        a.add_argument("config")
        a.add_argument("--fetch", action="store_true", help="download missing raw data first (network)")
        a.add_argument("--skip-if-no-data", action="store_true", help="exit 0 if real data are not cached")
        a.set_defaults(func=fn)

    r = sub.add_parser("report", help="build reports/<name>/RESULTS.md and figures from stored results")
    r.add_argument("config")
    r.set_defaults(func=_cmd_report)

    d = sub.add_parser("dashboard", help="build reports/dashboard/index.html from all stored results")
    d.add_argument("config", nargs="?", help="ignored (the dashboard includes every run)")
    d.set_defaults(func=_cmd_dashboard)

    dr = sub.add_parser("doctor", help="check environment, data cache and model availability")
    dr.add_argument("--online", action="store_true", help="also try to download missing model weights")
    dr.set_defaults(func=_cmd_doctor)

    fc = sub.add_parser("flashcards", help="export all lesson flashcards to flashcards.csv (Anki)")
    fc.set_defaults(func=_cmd_flashcards)

    pb = sub.add_parser("publish-results", help="export stored statistics to versioned JSON for the website")
    pb.add_argument("runs", nargs="*", help="run names under results/ (default: every run with statistics)")
    pb.set_defaults(func=_cmd_publish)

    e = sub.add_parser("evaluate", help="recompute statistics from stored forecasts")
    e.add_argument("config")
    e.set_defaults(func=_cmd_evaluate)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(logging.DEBUG if args.verbose else logging.INFO)
    return int(args.func(args) or 0)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
