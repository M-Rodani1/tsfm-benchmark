"""Reports are pure functions of stored artifacts (traceability of every number)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tsfm_rc.config import load_config
from tsfm_rc.paths import REPORTS_DIR, RESULTS_DIR
from tsfm_rc.reports.results_md import fp, md_table, render

SMOKE = RESULTS_DIR / "smoke"
needs_smoke = pytest.mark.skipif(not (SMOKE / "stats").exists(), reason="run `make smoke` first")


@needs_smoke
def test_committed_report_is_exactly_the_render_of_committed_artifacts(tmp_path):
    """If this fails, reports/smoke/RESULTS.md was edited by hand or is stale: run `make smoke`."""
    cfg = load_config("configs/smoke.yaml")
    text = render(cfg, SMOKE, tmp_path, make_figures=True)
    committed = (REPORTS_DIR / "smoke" / "RESULTS.md").read_text(encoding="utf-8")
    assert text == committed


@needs_smoke
def test_render_is_deterministic_including_figures(tmp_path):
    cfg = load_config("configs/smoke.yaml")
    a, b = tmp_path / "a", tmp_path / "b"
    assert render(cfg, SMOKE, a) == render(cfg, SMOKE, b)
    svgs = sorted(p.name for p in (a / "figures").glob("*.svg"))
    assert svgs
    for name in svgs:
        assert (a / "figures" / name).read_bytes() == (b / "figures" / name).read_bytes(), name


@needs_smoke
def test_report_states_data_source_and_unavailable_models(tmp_path):
    cfg = load_config("configs/smoke.yaml")
    text = render(cfg, SMOKE, tmp_path, make_figures=False)
    assert "SYNTHETIC FIXTURE DATA" in text
    assert "## 3. Which conclusions survive multiple-testing correction" in text
    assert "## 12. Limitations" in text and "## 13. Provenance" in text
    for f in ("stats/dm_all.parquet", "forecasts_baselines.parquet"):
        assert f in text  # every artifact is listed with its hash


@needs_smoke
def test_report_fails_loudly_without_stats(tmp_path):
    cfg = load_config("configs/smoke.yaml")
    shutil.copytree(SMOKE, tmp_path / "run", ignore=shutil.ignore_patterns("stats"))
    text = render(cfg, tmp_path / "run", tmp_path / "rep", make_figures=False)
    assert "*(not computed)*" in text  # never invents numbers for missing tables


def test_formatting_helpers():
    import pandas as pd

    assert fp(0.0004) == "<0.001" and fp(0.0123) == "0.012" and fp(float("nan")) == "–"
    t = md_table(pd.DataFrame({"a": [1], "b": ["x"]}))
    assert t.splitlines()[0] == "| a | b |" and t.splitlines()[2] == "| 1 | x |"


def test_index_prefers_most_complete_run(tmp_path):
    from tsfm_rc.reports.results_md import write_index

    for name in ("smoke", "default_fixtures"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "RESULTS.md").write_text(f"# Results: `{name}`\n![x](figures/f.png)\n")
    text = write_index(Path(tmp_path)).read_text()
    assert "**`default_fixtures`** run" in text and "default_fixtures/figures/f.png" in text
