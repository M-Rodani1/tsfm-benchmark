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
