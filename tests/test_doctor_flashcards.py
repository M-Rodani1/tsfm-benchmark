"""`make doctor` and `make flashcards`."""

from __future__ import annotations

import csv

from tsfm_rc.pipeline import doctor, flashcards


def test_doctor_runs_and_reports_fixes(capsys):
    rc = doctor.run_doctor(online=False)
    out = capsys.readouterr().out
    assert "Python" in out and "fixtures" in out and "results" in out
    assert rc == 0  # nothing *required* is missing in the test environment
    for line in out.splitlines():
        if "WARN" in line or "FAIL" in line:
            break
    else:
        return
    assert "→" in out  # every warning/failure comes with a plain-English fix


def test_doctor_detects_tampered_fixture(tmp_path, monkeypatch):
    import shutil

    from tsfm_rc.paths import FIXTURE_DIR

    fx = tmp_path / "fixtures"
    shutil.copytree(FIXTURE_DIR, fx)
    with open(fx / "synthetic_ohlcv.csv", "a", encoding="utf-8") as fh:
        fh.write("tampered\n")
    monkeypatch.setattr(doctor, "FIXTURE_DIR", fx)
    c = doctor.check_fixtures()
    assert c.status == "FAIL" and "git checkout" in c.fix


def test_flashcards_export_anki_csv(tmp_path):
    out = flashcards.export(tmp_path / "cards.csv")
    rows = list(csv.reader(open(out, encoding="utf-8")))
    assert len(rows) >= 55  # 11 lessons x 5-10 cards
    assert all(len(r) == 3 and r[0] and r[1] for r in rows)
    assert all(r[2].startswith("tsfm_rc lesson_") for r in rows)
    lessons = {r[2].split()[1] for r in rows}
    assert len(lessons) >= 10


def test_doctor_fix_catalog_is_exported_for_the_site():
    """The website's terminal-task pages show the doctor's own fix messages
    (site/content/doctor_fixes.json, written by `make lessons`): it must be up to date, and every
    fix message in the catalog must be one the doctor actually uses."""
    import inspect
    import json

    from tsfm_rc.paths import ROOT

    committed = json.loads((ROOT / "site" / "content" / "doctor_fixes.json").read_text(encoding="utf-8"))
    assert committed == doctor.fix_catalog(), "stale: run `make lessons`"
    src = inspect.getsource(doctor)
    for key in doctor.FIXES:
        assert f'_fix("{key}")' in src, f"fix {key} is not used by any check"


def test_site_output_markers_match_the_cli():
    """site/src/lib/cliparse.ts recognises pasted terminal output by these exact strings; if the
    CLI's wording changes, this test fails so the site's checker is updated with it."""
    from tsfm_rc.paths import ROOT

    site = (ROOT / "site" / "src" / "lib" / "cliparse.ts").read_text(encoding="utf-8")
    python = {
        "doctor": (ROOT / "src" / "tsfm_rc" / "pipeline" / "doctor.py").read_text(encoding="utf-8"),
        "cli": (ROOT / "src" / "tsfm_rc" / "cli.py").read_text(encoding="utf-8"),
        "run": (ROOT / "src" / "tsfm_rc" / "pipeline" / "run.py").read_text(encoding="utf-8"),
    }
    markers = {
        "doctor": ["All checks passed.", "Everything needed for tests, lessons and `make smoke` works.",
                   "problem(s) to fix (✗)", '"OK": "✓", "WARN": "!", "FAIL": "✗"', "→ {c.fix}"],
        "cli": ["ticker(s) failed.", "[publish] no real-data run published yet", "[publish] {e['run']}: version",
                'or "real data"', "[report] {path} (index:", "open it in any browser", "[validate] {args.config}: OK"],
        "run": ["[data] no data available; stopping.", 'print(f"[tsfm] {name}: {msg}")', "[evaluate] {len(tables)} tables ->",
                'else f"UNAVAILABLE: '],
    }
    for where, items in markers.items():
        for m in items:
            assert m in python[where], f"{where}: CLI no longer prints {m!r}; update site/src/lib/cliparse.ts"
    # and the site's parser still looks for them
    for m in ["All checks passed", "Everything needed for tests, lessons and `make smoke` works", "problem\\(s\\) to fix",
              "ticker\\(s\\) failed", "no real-data run published yet", "real data", "open it in any browser",
              "no data available; stopping", "AVAILABLE|UNAVAILABLE", "\\[evaluate\\]", "\\[validate\\]"]:
        assert m in site, f"site parser lost marker {m!r}"
