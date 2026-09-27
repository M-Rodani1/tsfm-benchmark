"""Lesson-track checks: structure, word budget, notebook sync, and execution.

Execution tests run each notebook twice:
1. with the exercise cell replaced by ``solution.py``: every cell must succeed;
2. as shipped (unsolved stub): the checker cell must fail, proving it is not vacuous.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import nbformat
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
LESSONS = ROOT / "lessons"
sys.path.insert(0, str(LESSONS / "_tools"))
from build_notebooks import build_notebook, lesson_dirs  # noqa: E402

DIRS = [d for d in lesson_dirs() if (d / "lesson.py").exists()]
IDS = [d.name for d in DIRS]
WORD_LIMIT = 650  # "about 600 words of prose" (README + markdown cells, excl. flashcards)


def _words(text: str) -> int:
    text = re.sub(r"`[^`]*`", " x ", text)  # inline code counts as one token
    text = re.sub(r"\|[-:| ]+\|", " ", text)  # table separator rows
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-]*", text))


def test_at_least_ten_lessons_eventually():
    # Enforced strictly in Build 08; before that we only check numbering is sane.
    nums = [int(d.name[:2]) for d in DIRS]
    assert nums == sorted(nums) and len(set(nums)) == len(nums)


@pytest.mark.parametrize("d", DIRS, ids=IDS)
def test_lesson_structure(d: Path):
    for f in ("README.md", "lesson.py", "lesson.ipynb", "solution.py", "checker.py", "flashcards.yaml"):
        assert (d / f).exists(), f"{d.name} is missing {f}"
    readme = (d / "README.md").read_text(encoding="utf-8")
    for needle in ("minutes", "You'll be able to", "You need", "Common errors", "Next"):
        assert needle in readme, f"{d.name}/README.md lacks '{needle}'"
    cards = yaml.safe_load((d / "flashcards.yaml").read_text(encoding="utf-8"))
    assert 5 <= len(cards) <= 10, f"{d.name}: need 5-10 flashcards, found {len(cards)}"
    nb = nbformat.read(d / "lesson.ipynb", as_version=4)
    tags = [t for c in nb.cells for t in c.metadata.get("tags", [])]
    assert tags.count("exercise") == 1 and tags.count("checker") == 1
    first = nb.cells[0].source
    assert "You'll be able to" in first and "You need" in first and "min" in first
    assert "Next:" in nb.cells[-1].source, "notebook must end with 'Next: open lesson …'"
    assert any("Predict" in c.source for c in nb.cells if c.cell_type == "markdown"), \
        "need at least one 'predict before you run' prompt"


@pytest.mark.parametrize("d", DIRS, ids=IDS)
def test_word_budget(d: Path):
    readme = (d / "README.md").read_text(encoding="utf-8")
    nb = nbformat.read(d / "lesson.ipynb", as_version=4)
    md = [c.source for c in nb.cells if c.cell_type == "markdown" and "flashcards" not in c.metadata.get("tags", [])]
    n = _words(readme) + sum(_words(m) for m in md)
    assert n <= WORD_LIMIT, f"{d.name}: {n} words of prose (limit {WORD_LIMIT})"


@pytest.mark.parametrize("d", DIRS, ids=IDS)
def test_notebook_in_sync_with_source(d: Path):
    built = build_notebook(d)
    shipped = nbformat.read(d / "lesson.ipynb", as_version=4)
    assert [c.source for c in built.cells] == [c.source for c in shipped.cells], (
        f"{d.name}/lesson.ipynb is stale: run `make lessons`"
    )


def _execute(nb, d: Path):
    from nbclient import NotebookClient

    client = NotebookClient(
        nb, timeout=600, kernel_name="python3", allow_errors=True,
        resources={"metadata": {"path": str(d)}},
    )
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
@pytest.mark.parametrize("d", DIRS, ids=IDS)
def test_notebook_runs_with_solution(d: Path):
    nb = nbformat.read(d / "lesson.ipynb", as_version=4)
    sol = (d / "solution.py").read_text(encoding="utf-8")
    for c in nb.cells:
        if "exercise" in c.metadata.get("tags", []):
            c.source = sol
    nb = _execute(nb, d)
    errs = _errors(nb)
    assert not errs, f"{d.name}: errors with solution: {errs}"
    checker_out = "".join(
        o.get("text", "") for c in nb.cells if "checker" in c.metadata.get("tags", [])
        for o in c.get("outputs", [])
    )
    assert "Correct" in checker_out


@pytest.mark.notebooks
@pytest.mark.parametrize("d", DIRS, ids=IDS)
def test_checker_rejects_unsolved_stub(d: Path):
    nb = nbformat.read(d / "lesson.ipynb", as_version=4)
    nb = _execute(nb, d)
    errs = _errors(nb)
    assert errs, f"{d.name}: the unsolved notebook raised no error, so the checker is vacuous"
    assert all("checker" in tags for tags, _, _ in errs), f"{d.name}: unexpected errors {errs}"
