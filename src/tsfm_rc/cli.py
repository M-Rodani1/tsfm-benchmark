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
            "`provider: csv` with `csv_dir:` in the config (see docs/DECISIONS.md)."
        )
    return 1 if failed else 0


def stage_data(cfg, *, allow_fetch: bool):
    """Load (and optionally fetch) the cleaned panel; write the cleaning report."""
    from tsfm_rc.data.panel import load_panel

    panel = load_panel(cfg, allow_fetch=allow_fetch)
    out = cfg.run_dir
    out.mkdir(parents=True, exist_ok=True)
    panel.cleaning.to_frame().to_csv(out / "cleaning_report.csv", index=False)
    print(
        f"[data] {len(panel.tickers)} tickers loaded from {panel.source}; "
        f"{len(panel.unavailable)} unavailable; {len(panel.cleaning.rows)} cleaning events; "
        f"raw_hash={panel.raw_hash[:12]} panel_hash={panel.panel_hash[:12]}"
    )
    return panel


def run_provenance(cfg, panel, **extra):
    from tsfm_rc.provenance import provenance_record

    return provenance_record(
        config_hash=config_hash(cfg),
        data_hash=panel.panel_hash,
        extra={"raw_hash": panel.raw_hash, "data_source": panel.source, "config_name": cfg.name, **extra},
    )


def stage_baselines(cfg, panel):
    """Walk-forward forecasts for every baseline -> forecasts_baselines.parquet."""
    import time

    from tsfm_rc.engine.walkforward import run_baselines
    from tsfm_rc.provenance import write_parquet_with_provenance

    t0 = time.time()
    fc = run_baselines(panel.daily, panel.calendar, cfg)
    secs = time.time() - t0
    path = cfg.run_dir / "forecasts_baselines.parquet"
    write_parquet_with_provenance(fc, path, run_provenance(cfg, panel, stage="baselines", seconds=round(secs, 1)))
    print(f"[baselines] {len(fc):,} forecast rows in {secs:.0f}s -> {path}")
    return fc


def stage_tsfms(cfg, panel):
    """Zero-shot TSFM forecasts -> forecasts_tsfm.parquet and model_status.json."""
    import time

    from tsfm_rc.engine.tsfm_runner import load_backends, run_tsfms, write_status
    from tsfm_rc.provenance import write_parquet_with_provenance

    t0 = time.time()
    loaded = load_backends(cfg)
    fc, status = run_tsfms(panel.daily, panel.calendar, cfg, loaded=loaded)
    write_status(status, cfg.run_dir / "model_status.json")
    write_parquet_with_provenance(fc, cfg.run_dir / "forecasts_tsfm.parquet",
                                  run_provenance(cfg, panel, stage="tsfm", model_status=status))
    for name, st in status.items():
        msg = st["status"] if st["status"] == "AVAILABLE" else f"UNAVAILABLE: {st['reason'][:160]}"
        print(f"[tsfm] {name}: {msg}")
    print(f"[tsfm] {len(fc):,} forecast rows in {time.time() - t0:.0f}s")
    return fc, status, loaded


def stage_synthetic(cfg, panel, loaded=None):
    """Synthetic-control experiment -> forecasts_synthetic.parquet and synthetic_meta.json."""
    import json
    import time

    from tsfm_rc.contamination.synthetic_control import run_synthetic_control
    from tsfm_rc.engine.tsfm_runner import run_tsfms
    from tsfm_rc.provenance import write_parquet_with_provenance

    if not cfg.synthetic.enabled:
        return None
    t0 = time.time()
    calib = cfg.economic.asset if cfg.economic.asset in panel.daily else panel.tickers[0]
    fc, meta = run_synthetic_control(cfg, panel.daily[calib],
                                     run_tsfms_fn=lambda d, cal, c: run_tsfms(d, cal, c, loaded=loaded))
    meta["calibration_asset"] = calib
    write_parquet_with_provenance(fc, cfg.run_dir / "forecasts_synthetic.parquet",
                                  run_provenance(cfg, panel, stage="synthetic_control", synthetic_meta=meta))
    with open(cfg.run_dir / "synthetic_meta.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, default=str)
    print(f"[synthetic] {fc['ticker'].nunique()} simulated series, {len(fc):,} rows in {time.time() - t0:.0f}s")
    return fc


def _cmd_all(args: argparse.Namespace) -> int:
    """Run every pipeline stage implemented so far for one config."""
    cfg = load_config(args.config)
    print(f"[validate] {args.config}: OK (config_hash={config_hash(cfg)[:16]})")
    panel = stage_data(cfg, allow_fetch=args.fetch)
    if not panel.tickers:
        print("[data] no data available; stopping. Run `make fetch-data` (needs network).")
        return 1
    stage_baselines(cfg, panel)
    _, _, loaded = stage_tsfms(cfg, panel)
    stage_synthetic(cfg, panel, loaded)
    # Later builds append stages here (evaluate, report, dashboard).
    return 0


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
