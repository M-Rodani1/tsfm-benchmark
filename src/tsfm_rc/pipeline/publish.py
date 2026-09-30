"""``make publish-results``: export stored results to versioned JSON for the website.

For every run in ``results/`` that has statistics, this writes (under
``site/public/data/results/``):

- ``<run>/<version>/payload.json``: the dashboard view of the run (the same data
  ``reports/dashboard/index.html`` embeds: primary tests, DM tables, MCS, contamination,
  cumulative loss differentials, windows, model status) plus the report's limitations;
- ``<run>/<version>/tables/<table>.json``: the stored statistics tables the lessons read
  (pandas ``orient="table"`` layout, floats written with their exact round-trip repr);
- ``<run>/<version>/RESULTS.md``: a copy of the generated report;
- ``index.json``: one entry per run with its version, provenance (config hash, data hash,
  git commit), model status, a SYNTHETIC label for fixture runs, and a publish history.

The version is the first 12 hex digits of the SHA-256 of everything written for the run,
so publishing unchanged results is a no-op and any change gets a new, cache-busting path.
Only the current version of each run is kept on disk; ``history`` keeps the trace.

Only *derived* results are exported. Raw prices (``data/raw``), row-level forecasts and
row-level losses never leave the machine (the site shows no raw price data).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from tsfm_rc.paths import REPORTS_DIR, RESULTS_DIR, ROOT
from tsfm_rc.provenance import read_parquet_provenance
from tsfm_rc.reports.dashboard import RUN_ORDER, run_payload

PUBLISH_ROOT = ROOT / "site" / "public" / "data" / "results"
LESSON_TABLES = ("dm_primary", "dm_all", "dm_per_asset", "mcs", "metrics", "probabilistic", "contamination",
                 "economic", "synthetic", "windows", "data_quality", "scales")
NEVER_PUBLISH = ("losses", "losses_primary", "loss_diff_series")  # row-level; the series is in the payload
SYNTHETIC_LABEL = "SYNTHETIC — not research results"
REAL_SOURCES = ("yfinance", "csv")


def _dumps(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _clean(obj):
    """NaN/inf -> None, numpy scalars -> Python, recursively (JSON has no NaN)."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        return f if np.isfinite(f) else None
    return obj


def _cell(v):
    if v is None or v is pd.NaT:
        return None
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        f = float(v)
        return f if np.isfinite(f) else None
    return v


def table_json(df: pd.DataFrame) -> str:
    """pandas "table" JSON (schema + records) with shortest round-trip float repr, so that
    ``pd.read_json(..., orient="table", precise_float=True)`` returns exactly the stored values."""
    from pandas.io.json import build_table_schema

    df = df.reset_index(drop=True)
    schema = build_table_schema(df, index=False, version=False)
    data = [{c: _cell(v) for c, v in zip(df.columns, row, strict=True)} for row in df.itertuples(index=False, name=None)]
    return json.dumps({"schema": schema, "data": data}, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _limitations(run_dir: Path) -> str:
    from tsfm_rc.reports.results_md import _limitations as lim
    from tsfm_rc.reports.results_md import load_tables

    prov = read_parquet_provenance(run_dir / "stats" / "dm_all.parquet")
    status = json.loads((run_dir / "model_status.json").read_text()) if (run_dir / "model_status.json").exists() else {}
    lines = lim(load_tables(run_dir), prov, status)
    return "\n".join(line for line in lines if not line.startswith("## ")).strip() + "\n"


def build_run_files(run_dir: Path) -> tuple[dict[str, str], dict] | None:
    """All files for one run (relative path within the version dir -> text) and metadata."""
    payload = run_payload(run_dir)
    if payload is None:
        return None
    prov = read_parquet_provenance(run_dir / "stats" / "dm_all.parquet")
    status = json.loads((run_dir / "model_status.json").read_text()) if (run_dir / "model_status.json").exists() else {}
    source = prov.get("data_source", "?")
    synthetic = source not in REAL_SOURCES
    payload = {**payload, "synthetic": synthetic, "label": SYNTHETIC_LABEL if synthetic else "",
               "limitations_md": _limitations(run_dir)}
    files = {"payload.json": _dumps(_clean(payload))}
    tables = {}
    for t in LESSON_TABLES:
        p = run_dir / "stats" / f"{t}.parquet"
        if p.exists():
            files[f"tables/{t}.json"] = table_json(pd.read_parquet(p))
            tables[t] = f"tables/{t}.json"
    report = REPORTS_DIR / run_dir.name / "RESULTS.md"
    if report.exists():
        files["RESULTS.md"] = report.read_text(encoding="utf-8")
    git = prov.get("git", {})
    meta = {
        "run": run_dir.name,
        "synthetic": synthetic,
        "label": SYNTHETIC_LABEL if synthetic else "",
        "data_source": source,
        "provenance": {"config_hash": prov.get("config_hash"), "data_hash": prov.get("data_hash"),
                       "raw_hash": prov.get("raw_hash"), "git_commit": git.get("commit"), "git_dirty": git.get("dirty"),
                       "created_utc": prov.get("created_utc")},
        "model_status": {m: {k: s.get(k) for k in ("status", "reason", "release_date", "resolved_revision", "weights_commit_date",
                                                   "hf_id") if s.get(k) is not None}
                         for m, s in status.items()},
        "tables": tables,
    }
    return files, _clean(meta)


def _version(files: dict[str, str]) -> str:
    h = hashlib.sha256()
    for name in sorted(files):
        h.update(name.encode())
        h.update(b"\0")
        h.update(files[name].encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()[:12]


# Display names for the website only (presentation; the study identifies models by config name).
MODEL_LABELS = {"chronos_bolt_tiny": "Chronos-Bolt tiny", "timesfm_2p5_200m": "TimesFM 2.5 (200M)", "moirai_1p1_small": "Moirai 1.1 small"}


def study_facts(config_path: str = "configs/default.yaml", results_root: Path = RESULTS_DIR) -> dict:
    """What the pre-registered study is, for the website's Home page (``study.json``).

    Everything comes from the config and the contamination-window rule
    (``tsfm_rc.contamination.windows``): clean test data start at the effective release plus the
    buffer. Once a real run exists, the weights' commit dates in its ``model_status.json`` enter
    exactly as they do in the study (amendment A1). No date is typed by hand.
    """
    from tsfm_rc.config import config_hash, load_config
    from tsfm_rc.contamination.windows import windows_for_models

    cfg = load_config(ROOT / config_path)
    status_path = results_root / cfg.name / "model_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
    windows = windows_for_models(cfg, status)
    return {
        "generated_by": "tsfm_rc.pipeline.publish.study_facts (make publish-results)",
        "config": str(config_path), "config_hash": config_hash(cfg)[:16], "run": cfg.name,
        "data": {"provider": cfg.data.provider, "tickers": len(cfg.data.tickers), "start": str(cfg.data.start),
                 "end": str(cfg.data.end)},
        "targets": list(cfg.targets.kinds), "horizons": list(cfg.targets.horizons),
        "baselines": sorted({b for names in cfg.models.baselines.values() for b in names}),
        "primary_tests": len(cfg.models.tsfms) * len(cfg.targets.kinds) * len(cfg.targets.horizons),
        "buffer_days": cfg.contamination.buffer_days,
        "weights_dates_from": str(status_path.relative_to(results_root.parent)) if status else None,
        "models": [{"name": m.name, "label": MODEL_LABELS.get(m.name, m.name), "hf_id": m.hf_id, **{
            k: v for k, v in windows[m.name].as_dict().items() if k in ("release_date", "weights_date", "effective_release", "clean_start")}}
            for m in cfg.models.tsfms],
    }


def publish(runs: list[str] | None = None, results_root: Path = RESULTS_DIR, out_root: Path = PUBLISH_ROOT,
            now: str | None = None) -> dict:
    out_root.mkdir(parents=True, exist_ok=True)
    index_path = out_root / "index.json"
    old = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"runs": []}
    old_by_run = {r["run"]: r for r in old.get("runs", [])}
    names = runs or [n for n in RUN_ORDER + sorted(p.name for p in results_root.iterdir() if p.is_dir())
                     if (results_root / n / "stats" / "dm_all.parquet").exists()]
    names = list(dict.fromkeys(names))
    now = now or dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    entries = {r: e for r, e in old_by_run.items() if r not in names and (out_root / r).exists()}
    for name in names:
        built = build_run_files(results_root / name)
        if built is None:
            raise FileNotFoundError(f"results/{name} has no statistics; run the pipeline first")
        files, meta = built
        version = _version(files)
        prev = old_by_run.get(name, {})
        run_dir = out_root / name
        vdir = run_dir / version
        if prev.get("version") != version or not vdir.exists():
            if run_dir.exists():
                shutil.rmtree(run_dir)
            for rel, text in files.items():
                p = vdir / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
            published = now
            history = [*prev.get("history", []), {"version": version, "published_utc": now,
                                                   "git_commit": meta["provenance"]["git_commit"]}][-20:]
        else:
            published = prev["published_utc"]
            history = prev.get("history", [])
        entries[name] = {
            **meta, "version": version, "published_utc": published, "history": history,
            "payload": f"{name}/{version}/payload.json",
            "report": f"{name}/{version}/RESULTS.md" if "RESULTS.md" in files else None,
            "tables": {t: f"{name}/{version}/{rel}" for t, rel in meta["tables"].items()},
        }
    order = {n: i for i, n in enumerate(RUN_ORDER)}
    runs_out = sorted(entries.values(), key=lambda e: (order.get(e["run"], 99), e["run"]))
    index = {"schema": 1, "generated_by": "tsfm-rc publish-results",
             "real_results_available": any(not e["synthetic"] for e in runs_out), "runs": runs_out}
    text = json.dumps(index, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if not index_path.exists() or index_path.read_text(encoding="utf-8") != text:
        index_path.write_text(text, encoding="utf-8")
    facts = json.dumps(study_facts(results_root=results_root), indent=1, ensure_ascii=False) + "\n"
    study_path = out_root / "study.json"
    if not study_path.exists() or study_path.read_text(encoding="utf-8") != facts:
        study_path.write_text(facts, encoding="utf-8")
    return index
