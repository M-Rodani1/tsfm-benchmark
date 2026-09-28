"""Amendment A4: stride-1 origins in the clean windows for the primary family.

- the primary pass has its own origin schedule, model set and re-fit rule;
- every secondary table in the committed fixture results is unchanged, column by column,
  relative to the results committed before A4 (fingerprints in tests/data).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tsfm_rc.config import load_config
from tsfm_rc.data.panel import load_panel
from tsfm_rc.engine.walkforward import (
    build_origins,
    build_primary_origins,
    primary_pass_models,
    primary_pass_start,
    run_primary_baselines,
)
from tsfm_rc.hashing import column_fingerprints
from tsfm_rc.models.registry import refit_every
from tsfm_rc.paths import ROOT

FINGERPRINTS = json.loads((ROOT / "tests" / "data" / "pre_a4_table_fingerprints.json").read_text())


def test_primary_schedule_is_stride1_from_earliest_clean_start():
    cfg = load_config("configs/default.yaml")
    start = primary_pass_start(cfg)
    # Moirai 1.1 is the earliest release (2024-06-30) + 30-day buffer
    assert start == pd.Timestamp("2024-07-30")
    cal = pd.bdate_range("2014-01-01", "2026-09-25")
    o = build_primary_origins(cal, cfg)
    assert o[0].timestamp == pd.Timestamp("2024-07-30")
    assert (np.diff(cal.get_indexer([x.timestamp for x in o])) == 1).all()
    # an explicit start (a model's own clean start) is honoured; never before test_start
    assert build_primary_origins(cal, cfg, start="2025-10-15")[0].timestamp == pd.Timestamp("2025-10-15")
    assert build_primary_origins(cal, cfg, start="2001-01-01")[0].timestamp >= pd.Timestamp(cfg.evaluation.test_start)
    # the main schedule is untouched
    main = build_origins(cal, cfg)
    assert (np.diff(cal.get_indexer([x.timestamp for x in main])) == 5).all()


def test_primary_pass_models_and_refit_scaling():
    cfg = load_config("configs/default.yaml")
    assert primary_pass_models(cfg, "returns") == ("zero", "ar_bic")
    assert primary_pass_models(cfg, "rv") == ("har", "garch")
    assert primary_pass_models(cfg, "volume") == ("har", "ar_bic")
    # same interval in trading days: GARCH every 4 origins at stride 5 = every 20 at stride 1
    assert refit_every("garch", cfg) == 4 and refit_every("garch", cfg, stride=1) == 20
    assert refit_every("lgbm", cfg, stride=1) == 250
    assert refit_every("har", cfg, stride=1) == 1 and refit_every("har", cfg) == 1
    assert refit_every("garch", cfg, stride=5) == 4


def test_primary_pass_refits_garch_every_scaled_interval():
    cfg = load_config("configs/smoke.yaml")
    panel = load_panel(cfg)
    one = {"SYN_GARCH_A": panel.daily["SYN_GARCH_A"]}
    fc = run_primary_baselines(one, panel.daily["SYN_GARCH_A"].index, cfg, n_jobs=1)
    g = fc[(fc["model"] == "garch") & (fc["horizon"] == 1)].sort_values("origin")
    k = refit_every("garch", cfg, stride=1)  # smoke: 8 origins at stride 10 = 80 at stride 1
    assert k == 80
    assert np.flatnonzero(g["refit"].to_numpy()).tolist() == list(range(0, len(g), k))
    assert set(fc["model"]) == {"zero", "ar_bic", "har", "garch"} and set(fc["window"]) == {"expanding"}


@pytest.mark.parametrize("run", sorted(FINGERPRINTS["runs"]))
def test_secondary_tables_unchanged_by_a4(run):
    """Every column of every secondary table committed before A4 is identical, cell by cell,
    in the committed results after A4 (new columns may be added; none may change)."""
    stats = ROOT / "results" / run / "stats"
    for table, fp in FINGERPRINTS["runs"][run].items():
        path = stats / f"{table}.parquet"
        if not path.exists():
            pytest.skip(f"{path} not present (not committed)")
        now = column_fingerprints(pd.read_parquet(path))
        assert now["n_rows"] == fp["n_rows"], (table, now["n_rows"], fp["n_rows"])
        changed = [c for c, h in fp["columns"].items() if now["columns"].get(c) != h]
        assert not changed, f"{run}/{table}: columns changed by A4: {changed}"


def test_fingerprint_detects_a_single_changed_cell():
    df = pd.DataFrame({"a": [1.0, 2.0, np.nan], "b": ["x", "y", "z"]})
    df2 = df.copy()
    df2.loc[1, "a"] = 2.0000000001
    assert column_fingerprints(df)["columns"]["b"] == column_fingerprints(df2)["columns"]["b"]
    assert column_fingerprints(df)["columns"]["a"] != column_fingerprints(df2)["columns"]["a"]
    assert column_fingerprints(df) == column_fingerprints(df.copy())


def test_committed_runs_have_primary_pass_artifacts():
    for run in ("smoke", "default_fixtures"):
        d = ROOT / "results" / run
        assert (d / "forecasts_baselines_primary.parquet").exists(), run
        fc = pd.read_parquet(d / "forecasts_baselines_primary.parquet")
        cal = pd.DatetimeIndex(sorted(fc["origin"].unique()))
        cfg = load_config(Path("configs") / f"{run}.yaml")
        assert cal.min() >= primary_pass_start(cfg)
        assert set(fc["window"]) == {"expanding"}
