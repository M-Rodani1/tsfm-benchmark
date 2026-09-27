"""Pipeline stages. Each stage reads/writes artifacts under ``results/<config name>/``.

    data        -> cleaning_report.csv
    baselines   -> forecasts_baselines.parquet
    tsfm        -> forecasts_tsfm.parquet, model_status.json
    synthetic   -> forecasts_synthetic.parquet, synthetic_meta.json
    evaluate    -> stats/<table>.parquet (every table carries provenance), provenance.json

Every Parquet file embeds a provenance record (config hash, data hashes, package versions,
git commit) in its metadata; see :mod:`tsfm_rc.provenance`.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import pandas as pd

from tsfm_rc.config import RunConfig, config_hash
from tsfm_rc.data.panel import Panel, load_panel
from tsfm_rc.provenance import provenance_record, write_parquet_with_provenance

log = logging.getLogger(__name__)


def run_provenance(cfg: RunConfig, panel: Panel, **extra) -> dict:
    return provenance_record(
        config_hash=config_hash(cfg),
        data_hash=panel.panel_hash,
        extra={"raw_hash": panel.raw_hash, "data_source": panel.source, "config_name": cfg.name, **extra},
    )


def stage_data(cfg: RunConfig, *, allow_fetch: bool) -> Panel:
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


def stage_baselines(cfg: RunConfig, panel: Panel) -> pd.DataFrame:
    from tsfm_rc.engine.walkforward import run_baselines

    t0 = time.time()
    fc = run_baselines(panel.daily, panel.calendar, cfg)
    secs = time.time() - t0
    path = cfg.run_dir / "forecasts_baselines.parquet"
    write_parquet_with_provenance(fc, path, run_provenance(cfg, panel, stage="baselines", seconds=round(secs, 1)))
    print(f"[baselines] {len(fc):,} forecast rows in {secs:.0f}s -> {path}")
    return fc


def stage_tsfms(cfg: RunConfig, panel: Panel):
    from tsfm_rc.engine.tsfm_runner import load_backends, run_tsfms, write_status

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


def stage_synthetic(cfg: RunConfig, panel: Panel, loaded=None):
    from tsfm_rc.contamination.synthetic_control import run_synthetic_control
    from tsfm_rc.engine.tsfm_runner import run_tsfms

    if not cfg.synthetic.enabled:
        return None, {}
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
    return fc, meta


def load_stored_forecasts(run_dir: Path) -> tuple[pd.DataFrame, dict, pd.DataFrame | None, dict]:
    parts = [pd.read_parquet(run_dir / f) for f in ("forecasts_baselines.parquet", "forecasts_tsfm.parquet")
             if (run_dir / f).exists()]
    fc = pd.concat([p for p in parts if len(p)], ignore_index=True)
    status = json.loads((run_dir / "model_status.json").read_text()) if (run_dir / "model_status.json").exists() else {}
    syn = pd.read_parquet(run_dir / "forecasts_synthetic.parquet") if (run_dir / "forecasts_synthetic.parquet").exists() else None
    meta = json.loads((run_dir / "synthetic_meta.json").read_text()) if (run_dir / "synthetic_meta.json").exists() else {}
    return fc, status, syn, meta


def stage_evaluate(cfg: RunConfig, panel: Panel) -> dict[str, pd.DataFrame]:
    from tsfm_rc.eval.evaluate import evaluate

    t0 = time.time()
    run_dir = cfg.run_dir
    fc, status, syn, meta = load_stored_forecasts(run_dir)
    tables = evaluate(fc, panel.daily, cfg, status, syn, meta.get("kappa", 1.0))
    prov = run_provenance(cfg, panel, stage="evaluate", model_status=status)
    stats_dir = run_dir / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        write_parquet_with_provenance(df.reset_index(drop=True), stats_dir / f"{name}.parquet", prov)
    with open(run_dir / "provenance.json", "w", encoding="utf-8") as fh:
        json.dump(prov, fh, indent=2, default=str)
    print(f"[evaluate] {len(tables)} tables -> {stats_dir} in {time.time() - t0:.0f}s")
    return tables


def run_all_stages(cfg: RunConfig, *, allow_fetch: bool) -> int:
    panel = stage_data(cfg, allow_fetch=allow_fetch)
    if not panel.tickers:
        print("[data] no data available; stopping. Run `make fetch-data` (needs network).")
        return 1
    stage_baselines(cfg, panel)
    _, _, loaded = stage_tsfms(cfg, panel)
    stage_synthetic(cfg, panel, loaded)
    stage_evaluate(cfg, panel)
    return 0
