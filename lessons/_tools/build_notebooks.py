"""Build ``lesson.ipynb`` from ``lesson.py`` (percent format) + ``flashcards.yaml``.

Source format (a subset of the jupytext "percent" format):

    # %% [markdown]
    # Some *markdown* text.
    # %%
    x = 1          # a code cell
    # %% tags=["exercise"]
    ...            # a tagged code cell

Run from the repo root:  ``make lessons``  (or ``uv run python lessons/_tools/build_notebooks.py``)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import nbformat
import yaml

LESSONS_DIR = Path(__file__).resolve().parents[1]
CELL_RE = re.compile(r"^# %%(?P<md> \[markdown\])?(?P<rest>.*)$")
TAGS_RE = re.compile(r"tags=(\[.*?\])")


def parse_percent(text: str) -> list[dict]:
    cells: list[dict] = []
    cur: dict | None = None
    for line in text.splitlines():
        m = CELL_RE.match(line)
        if m:
            if cur is not None:
                cells.append(cur)
            tags: list[str] = []
            t = TAGS_RE.search(m.group("rest") or "")
            if t:
                tags = json.loads(t.group(1))
            cur = {"type": "markdown" if m.group("md") else "code", "lines": [], "tags": tags}
            continue
        if cur is None:  # preamble before first marker is ignored
            continue
        if cur["type"] == "markdown":
            if line.startswith("# "):
                line = line[2:]
            elif line == "#":
                line = ""
        cur["lines"].append(line)
    if cur is not None:
        cells.append(cur)
    for c in cells:  # trim blank edges
        while c["lines"] and not c["lines"][-1].strip():
            c["lines"].pop()
        while c["lines"] and not c["lines"][0].strip():
            c["lines"].pop(0)
    return [c for c in cells if c["lines"]]


def load_flashcards(lesson_dir: Path) -> list[dict]:
    p = lesson_dir / "flashcards.yaml"
    if not p.exists():
        return []
    cards = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    for c in cards:
        if set(c) != {"q", "a"}:
            raise ValueError(f"{p}: each card needs exactly 'q' and 'a' keys, got {sorted(c)}")
    return cards


def flashcards_markdown(cards: list[dict]) -> str:
    lines = ["## Flashcards", "", "Cover the answer, say it out loud, then check. "
             "`make flashcards` exports these to Anki.", ""]
    for i, c in enumerate(cards, 1):
        lines.append(f"{i}. **Q:** {c['q'].strip()}  ")
        lines.append(f"   **A:** {c['a'].strip()}")
    return "\n".join(lines)


def build_notebook(lesson_dir: Path) -> nbformat.NotebookNode:
    src = (lesson_dir / "lesson.py").read_text(encoding="utf-8")
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nb.metadata["language_info"] = {"name": "python"}
    tail: list = []
    for i, c in enumerate(parse_percent(src)):
        body = "\n".join(c["lines"])
        cell = (
            nbformat.v4.new_markdown_cell(body)
            if c["type"] == "markdown"
            else nbformat.v4.new_code_cell(body)
        )
        cell["id"] = f"cell-{i:02d}"
        if c["tags"]:
            cell.metadata["tags"] = c["tags"]
        # cells tagged "after-flashcards" (e.g. "Next: open lesson Y") go last
        (tail if "after-flashcards" in c["tags"] else nb.cells).append(cell)
    cards = load_flashcards(lesson_dir)
    if cards:
        fc = nbformat.v4.new_markdown_cell(flashcards_markdown(cards))
        fc["id"] = "flashcards"
        fc.metadata["tags"] = ["flashcards"]
        nb.cells.append(fc)
    nb.cells.extend(tail)
    return nb


def lesson_dirs() -> list[Path]:
    return sorted(p for p in LESSONS_DIR.iterdir() if p.is_dir() and re.match(r"^\d\d-", p.name))


def main() -> int:
    for d in lesson_dirs():
        if not (d / "lesson.py").exists():
            continue
        nb = build_notebook(d)
        out = d / "lesson.ipynb"
        nbformat.write(nb, out)
        print(f"built {out.relative_to(LESSONS_DIR.parent)} ({len(nb.cells)} cells)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
