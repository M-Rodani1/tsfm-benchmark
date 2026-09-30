"""``make publish-results``: exported JSON equals the stored tables, is versioned, and leaks
no raw data. The committed ``site/public/data/results`` must match the committed results."""

from __future__ import annotations

import json
import shutil

import numpy as np
import pandas as pd
import pytest

from tsfm_rc import learn
from tsfm_rc.paths import RESULTS_DIR, ROOT
from tsfm_rc.pipeline.publish import (
    LESSON_TABLES,
    NEVER_PUBLISH,
    PUBLISH_ROOT,
    SYNTHETIC_LABEL,
    build_run_files,
    publish,
    study_facts,
)

RUNS = ["smoke", "default_fixtures"]


def test_committed_published_data_is_current():
    """Every committed run is published at the version its current results produce."""
    index = json.loads((PUBLISH_ROOT / "index.json").read_text(encoding="utf-8"))
    by_run = {e["run"]: e for e in index["runs"]}
    for run in RUNS:
        files, meta = build_run_files(RESULTS_DIR / run)
        from tsfm_rc.pipeline.publish import _version

        assert by_run[run]["version"] == _version(files), f"{run}: run `make publish-results` and commit"
        for rel, text in files.items():
            p = PUBLISH_ROOT / run / by_run[run]["version"] / rel
            assert p.read_text(encoding="utf-8") == text, p
    assert index["real_results_available"] is False  # only synthetic fixtures so far


def test_study_facts_are_current_and_derived_from_config():
    """Home's "Models under test" dates come from the config and the contamination rule, never typed."""
    from tsfm_rc.config import load_config
    from tsfm_rc.contamination.windows import windows_for_models

    facts = json.loads((PUBLISH_ROOT / "study.json").read_text(encoding="utf-8"))
    assert facts == json.loads(json.dumps(study_facts())), "run `make publish-results` and commit"
    cfg = load_config(ROOT / "configs" / "default.yaml")
    status_path = RESULTS_DIR / cfg.name / "model_status.json"
    windows = windows_for_models(cfg, json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {})
    assert [m["name"] for m in facts["models"]] == [m.name for m in cfg.models.tsfms]
    for m in facts["models"]:
        w = windows[m["name"]]
        assert m["clean_start"] == str(w.clean_start.date()) and m["effective_release"] == str(w.effective_release.date())
    assert facts["buffer_days"] == cfg.contamination.buffer_days
    assert facts["primary_tests"] == len(cfg.models.tsfms) * len(cfg.targets.kinds) * len(cfg.targets.horizons)


@pytest.mark.parametrize("run", RUNS)
def test_json_tables_equal_parquet(run, monkeypatch):
    for table in LESSON_TABLES:
        pq = RESULTS_DIR / run / "stats" / f"{table}.parquet"
        if not pq.exists():
            continue
        a = pd.read_parquet(pq)
        monkeypatch.setattr(learn, "_parquet_available", lambda: False)  # force the browser path
        b = learn.stats_table(run, table)
        monkeypatch.undo()
        assert list(a.columns) == list(b.columns) and len(a) == len(b), table
        for c in a.columns:
            x, y = a[c], b[c]
            if pd.api.types.is_float_dtype(x):
                np.testing.assert_allclose(y.astype(float), x, rtol=1e-13, atol=0, equal_nan=True, err_msg=f"{table}.{c}")
            elif pd.api.types.is_datetime64_any_dtype(x):
                assert (pd.to_datetime(y).values == x.values).sum() + (x.isna() & pd.to_datetime(y).isna()).sum() == len(x)
            else:
                assert [None if pd.isna(v) else v for v in x.tolist()] == [None if pd.isna(v) else v for v in y.tolist()], f"{table}.{c}"


def test_payload_is_labelled_and_has_provenance():
    index = json.loads((PUBLISH_ROOT / "index.json").read_text(encoding="utf-8"))
    for e in index["runs"]:
        payload = json.loads((PUBLISH_ROOT / e["payload"]).read_text(encoding="utf-8"))
        assert payload["synthetic"] is True and payload["label"] == SYNTHETIC_LABEL == e["label"]
        for k in ("config_hash", "data_hash", "git_commit"):
            assert e["provenance"][k], k
        assert payload["config_hash"] == e["provenance"]["config_hash"]
        assert "Limitations" not in payload["limitations_md"] and "Synthetic data" in payload["limitations_md"]


def test_no_raw_or_row_level_data_is_published():
    for p in (ROOT / "site" / "public").rglob("*"):
        assert "data/raw" not in p.as_posix()
        assert p.stem not in NEVER_PUBLISH, p
    for p in PUBLISH_ROOT.rglob("tables/*.json"):
        cols = {f["name"] for f in json.loads(p.read_text(encoding="utf-8"))["schema"]["fields"]}
        assert not cols & {"open", "high", "low", "close", "adj_close", "volume"}, p


def test_publish_is_idempotent_and_versioned(tmp_path):
    out = tmp_path / "pub"
    a = publish(["smoke"], out_root=out, now="2026-01-01T00:00:00+00:00")
    text = (out / "index.json").read_text()
    b = publish(["smoke"], out_root=out, now="2026-02-02T00:00:00+00:00")
    assert (out / "index.json").read_text() == text  # nothing changed -> nothing rewritten
    assert a["runs"][0]["version"] == b["runs"][0]["version"]
    assert b["runs"][0]["published_utc"] == "2026-01-01T00:00:00+00:00"
    # a changed result gets a new version, the old one is removed and kept in the history
    res = tmp_path / "results"
    shutil.copytree(RESULTS_DIR / "smoke", res / "smoke")
    df = pd.read_parquet(res / "smoke" / "stats" / "dm_all.parquet")
    from tsfm_rc.provenance import read_parquet_provenance, write_parquet_with_provenance

    prov = read_parquet_provenance(res / "smoke" / "stats" / "dm_all.parquet")
    write_parquet_with_provenance(df.assign(p_value=df["p_value"] * 0.5), res / "smoke" / "stats" / "dm_all.parquet", prov)
    c = publish(["smoke"], results_root=res, out_root=out, now="2026-03-03T00:00:00+00:00")
    e = c["runs"][0]
    assert e["version"] != a["runs"][0]["version"]
    assert [h["version"] for h in e["history"]] == [a["runs"][0]["version"], e["version"]]
    assert sorted(p.name for p in (out / "smoke").iterdir()) == [e["version"]]
