"""Lesson track: the single source in ``site/content`` and the generated notebooks in ``lessons/``.

- content rules (steps, <= 150 words between interactive elements, hints, flashcards, errors);
- ``lessons/`` is exactly what ``make lessons`` generates from ``site/content``;
- every lesson runs in a *browser-like* CPython sandbox (only the files the website mounts,
  no arch/lightgbm/pyarrow/torch): all cells succeed, the solution passes the checker and the
  unsolved starter fails it. The real browser run is ``site/e2e/exercises.spec.ts``;
- the generated notebooks execute in the full environment (marker ``notebooks``).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import nbformat
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
LESSONS = ROOT / "lessons"
sys.path.insert(0, str(LESSONS / "_tools"))
from build_notebooks import generated_files  # noqa: E402
from content import CONTENT_DIR, load_all, load_global_errors, validate  # noqa: E402

ALL = load_all()
BY_ID = {L.id: L for L in ALL}
IDS = [L.slug for L in ALL]


def test_at_least_ten_lessons_numbered_without_gaps():
    nums = [int(L.id) for L in ALL]
    assert len(ALL) >= 10, "the definition of done requires at least 10 lessons"
    assert nums == list(range(len(nums))), "lessons are numbered 00, 01, ... without gaps"
    assert [L.meta["next"] for L in ALL] == [f"{n:02d}" for n in range(1, len(ALL))] + [None]


def test_progress_file_lists_every_lesson():
    text = (LESSONS / "PROGRESS.md").read_text(encoding="utf-8")
    for L in ALL:
        assert f"| {L.id} " in text, f"PROGRESS.md lacks lesson {L.id}"


@pytest.mark.parametrize("L", ALL, ids=IDS)
def test_content_rules(L):
    assert validate(L, set(BY_ID)) == []


def test_global_error_table():
    errs = load_global_errors()
    assert len(errs) >= 15
    for e in errs:
        assert {"see", "match", "why", "fix"} <= set(e)
        re.compile(e["match"])
    text = " ".join(e["match"] for e in errs)
    for needle in ("broadcast", "IndexError", "KeyError", "dtype|convert", "NoneType", "NotImplementedError"):
        assert re.search(needle, text), f"no general explanation for {needle}"


@pytest.mark.parametrize("L", ALL, ids=IDS)
def test_generated_lesson_folder_is_up_to_date(L):
    for name, text in generated_files(L, BY_ID).items():
        p = LESSONS / L.slug / name
        assert p.exists() and p.read_text(encoding="utf-8") == text, f"lessons/{L.slug}/{name} is stale: run `make lessons`"


@pytest.mark.parametrize("L", ALL, ids=IDS)
def test_notebook_structure(L):
    nb = nbformat.read(LESSONS / L.slug / "lesson.ipynb", as_version=4)
    tags = [t for c in nb.cells for t in c.metadata.get("tags", [])]
    assert tags.count("exercise") == 1 and tags.count("checker") == 1
    first = nb.cells[0].source
    assert "You'll be able to" in first and "You need" in first and "min" in first
    assert "Next:" in nb.cells[-1].source
    assert any("Predict" in c.source for c in nb.cells if c.cell_type == "markdown")
    nxt = L.meta["next"]
    if nxt:
        assert f"lessons/{BY_ID[nxt].slug}/lesson.ipynb" in nb.cells[-1].source
    cards = yaml.safe_load((LESSONS / L.slug / "flashcards.yaml").read_text(encoding="utf-8"))
    assert 5 <= len(cards) <= 10


def _run(L, mode: str, browser_like: bool = True) -> dict:
    cmd = [sys.executable, str(LESSONS / "_tools" / "run_content.py"), str(L.dir), "--mode", mode]
    if browser_like:
        cmd.append("--browser-like")
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=900, cwd=ROOT)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("L", ALL, ids=IDS)
def test_lesson_runs_browser_like_and_checker_is_not_vacuous(L):
    solved = _run(L, "solution")
    bad = [c for c in solved["cells"] if not c["ok"]]
    assert not bad, f"{L.slug}: cells fail in the browser-like sandbox: {bad}"
    assert solved["checkpoint"]["passed"], f"{L.slug}: solution does not pass: {solved['checkpoint']}"
    stub = _run(L, "starter")
    assert not stub["checkpoint"]["passed"], f"{L.slug}: the unsolved starter passes, so the checker is vacuous"
    assert "NotImplementedError" in stub["checkpoint"].get("error", "")


def test_content_readme_documents_the_format():
    text = (CONTENT_DIR / "README.md").read_text(encoding="utf-8")
    for needle in ("```python", "```predict", "```checkpoint", "exercise.yaml", "errors.yaml", "150 words", "make lessons"):
        assert needle in text


# ------------------------------------------------------------------ generated notebooks (full env)
def _execute(nb, d: Path):
    from nbclient import NotebookClient

    client = NotebookClient(nb, timeout=600, kernel_name="python3", allow_errors=True,
                            resources={"metadata": {"path": str(d)}})
    client.execute()
    return nb


def _errors(nb):
    out = []
    for c in nb.cells:
        if c.cell_type != "code":
            continue
        for o in c.get("outputs", []):
            if o.get("output_type") == "error":
                out.append((c.metadata.get("tags", []), o["ename"], o["evalue"]))
    return out


@pytest.mark.notebooks
@pytest.mark.parametrize("L", ALL, ids=IDS)
def test_notebook_runs_with_solution(L):
    d = LESSONS / L.slug
    nb = nbformat.read(d / "lesson.ipynb", as_version=4)
    for c in nb.cells:
        if "exercise" in c.metadata.get("tags", []):
            c.source = (d / "solution.py").read_text(encoding="utf-8")
    nb = _execute(nb, d)
    assert not _errors(nb), f"{L.slug}: errors with solution: {_errors(nb)}"
    out = "".join(o.get("text", "") for c in nb.cells if "checker" in c.metadata.get("tags", []) for o in c.get("outputs", []))
    assert "Correct" in out


@pytest.mark.notebooks
@pytest.mark.parametrize("L", ALL, ids=IDS)
def test_notebook_checker_rejects_unsolved_stub(L):
    d = LESSONS / L.slug
    nb = _execute(nbformat.read(d / "lesson.ipynb", as_version=4), d)
    errs = _errors(nb)
    assert errs and all("checker" in tags for tags, _, _ in errs), f"{L.slug}: {errs}"
