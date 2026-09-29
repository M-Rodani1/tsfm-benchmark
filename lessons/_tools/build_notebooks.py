"""Generate the offline lesson track in ``lessons/`` from the single source in ``site/content``.

For every ``site/content/lessons/NN-slug/`` this writes ``lessons/NN-slug/``:

    lesson.ipynb     the notebook (steps as markdown + code cells, predict prompts with a
                     collapsible answer, the checkpoint exercise and its checker cell)
    lesson.py        the same notebook in "percent" format (readable diffs)
    solution.py, checker.py, flashcards.yaml, README.md, and any lesson assets

Do not edit those files by hand: edit ``site/content`` and run ``make lessons``.
``tests/test_lessons.py`` fails if the generated files are out of date.
"""

from __future__ import annotations

import sys
from pathlib import Path

import nbformat
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from content import Lesson, load_all  # noqa: E402

LESSONS_DIR = HERE.parent
GENERATED = "<!-- GENERATED from site/content/lessons/{slug} by `make lessons`: edit the source, not this file. -->"


def _predict_md(q: dict) -> str:
    lines = [f"🤔 **Predict before you run:** {q['question']}"]
    if q.get("figure"):
        lines += ["", "*(On the website this question comes with a chart of the series; it is drawn from "
                  f"`figures/{q['figure']}.json` in the lesson folder of `site/content`.)*"]
    if q.get("options"):
        lines += [""] + [f"- {o}" for o in q["options"]]
    if q.get("options") and isinstance(q.get("answer"), int):
        ans = q["options"][q["answer"]]
    elif q.get("answer") is not None:
        ans = f"{q['answer']}{q.get('unit', '')}"
    else:
        ans = ""
    lines += ["", "<details><summary>Answer (after you have predicted)</summary>", "",
              (f"**{ans}.** " if ans else "") + q["explain"], "", "</details>"]
    return "\n".join(lines)


def header_md(L: Lesson) -> str:
    m = L.meta
    code = ", ".join(f"`{c}`" for c in m.get("code_to_read", []))
    lines = [f"# Lesson {L.id}: {L.title}", f"⏱ **{m['minutes']} min**" + (f" · code you will read: {code}" if code else ""),
             "", "**You'll be able to…**"]
    lines += [f"{i}. {o}" for i, o in enumerate(m["objectives"], 1)]
    lines += ["", f"**You need:** {m['you_need']}"]
    return "\n".join(lines)


def next_md(L: Lesson, by_id: dict[str, Lesson]) -> str:
    nxt = L.meta.get("next")
    tick = f"Tick lesson {L.id} in `lessons/PROGRESS.md`."
    if nxt is None:
        return ("**Next:** you have finished the track. Run the real study (`make reproduce`, see README), re-read "
                f"`reports/RESULTS.md`, and draft your paper from `paper_template.md`. {tick}")
    n = by_id[nxt]
    return f"**Next:** open `lessons/{n.slug}/lesson.ipynb` ({n.title}). {tick}"


def flashcards_md(cards: list[dict]) -> str:
    lines = ["## Flashcards", "", "Cover the answer, say it out loud, then check. "
             "`make flashcards` exports these to Anki; the website schedules them for review.", ""]
    for i, c in enumerate(cards, 1):
        lines.append(f"{i}. **Q:** {str(c['q']).strip()}")
        lines.append(f"   - **A:** {str(c['a']).strip()}")
    return "\n".join(lines)


def cells(L: Lesson, by_id: dict[str, Lesson]) -> list[tuple[str, str, list[str]]]:
    """(type, source, tags) for every notebook cell."""
    out: list[tuple[str, str, list[str]]] = [("markdown", header_md(L), [])]
    for s in L.steps:
        md: list[str] = [f"## {s.title}"]
        for b in s.blocks:
            if b.kind == "md":
                md.append(b.text)
            elif b.kind == "predict":
                md.append(_predict_md(b.data))
            else:
                out.append(("markdown", "\n\n".join(md), []))
                md = []
                if b.kind == "python":
                    out.append(("code", b.text, []))
                else:  # checkpoint
                    out.append(("code", L.exercise.starter, ["exercise"]))
                    out.append(("code", f"from checker import check\ncheck({L.exercise.function})", ["checker"]))
        if md:
            out.append(("markdown", "\n\n".join(md), []))
    out = [c for c in out if c[1].strip()]
    out.append(("markdown", flashcards_md(L.flashcards), ["flashcards"]))
    out.append(("markdown", next_md(L, by_id), ["after-flashcards"]))
    return out


def notebook(L: Lesson, by_id: dict[str, Lesson]) -> nbformat.NotebookNode:
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nb.metadata["language_info"] = {"name": "python"}
    for i, (kind, src, tags) in enumerate(cells(L, by_id)):
        c = nbformat.v4.new_markdown_cell(src) if kind == "markdown" else nbformat.v4.new_code_cell(src)
        c["id"] = f"cell-{i:02d}"
        if tags:
            c.metadata["tags"] = tags
        nb.cells.append(c)
    return nb


def percent(L: Lesson, by_id: dict[str, Lesson]) -> str:
    parts = [f"# GENERATED from site/content/lessons/{L.slug} by `make lessons`: edit the source, not this file."]
    for kind, src, tags in cells(L, by_id):
        tag = f' tags={tags!r}'.replace("'", '"') if tags else ""
        if kind == "markdown":
            parts.append(f"# %% [markdown]{tag}\n" + "\n".join(f"# {x}" if x else "#" for x in src.splitlines()))
        else:
            parts.append(f"# %%{tag}\n{src}")
    return "\n\n".join(parts) + "\n"


def readme(L: Lesson, by_id: dict[str, Lesson]) -> str:
    m = L.meta
    pre = ", ".join(f"Lesson {p}" for p in m.get("prerequisites") or []) or "nothing"
    lines = [GENERATED.format(slug=L.slug), f"# Lesson {L.id}: {L.title}", "",
             f"⏱ **{m['minutes']} minutes** · Best on the website (Lessons → {L.id}); offline: open `lesson.ipynb`, "
             "run top to bottom, answer each 🤔 first.", "",
             "**You'll be able to:** " + " ".join(m["objectives"]), "",
             f"**You need:** {m['you_need']} (Prerequisites: {pre}.)", "",
             "**Stuck on the checkpoint?** Hints, in order:", ""]
    lines += [f"{i}. {h}" for i, h in enumerate(L.exercise.hints, 1)]
    lines += ["", "The full solution is `solution.py`, but try for 10 minutes first.", "", "## Common errors", "",
              "| You see | Why | Fix |", "|---|---|---|"]
    lines += [f"| {e['see']} | {e['why']} | {e['fix']} |" for e in L.errors]
    nxt = m.get("next")
    lines += ["", f"**Next:** Lesson {nxt} ({by_id[nxt].title})." if nxt else "**Next:** run the real study (`make reproduce`) and draft your paper."]
    return "\n".join(lines) + "\n"


def generated_files(L: Lesson, by_id: dict[str, Lesson]) -> dict[str, str]:
    files = {
        "lesson.ipynb": nbformat.writes(notebook(L, by_id)) + "\n",
        "lesson.py": percent(L, by_id),
        "solution.py": L.exercise.solution + "\n",
        "checker.py": L.exercise.checker,
        "flashcards.yaml": yaml.safe_dump(L.flashcards, allow_unicode=True, sort_keys=False, width=100),
        "README.md": readme(L, by_id),
    }
    for a in L.meta.get("assets") or []:
        files[a] = (L.dir / a).read_text(encoding="utf-8")
    return files


def build(out_root: Path = LESSONS_DIR) -> list[Path]:
    lessons = load_all()
    by_id = {L.id: L for L in lessons}
    written = []
    for L in lessons:
        d = out_root / L.slug
        d.mkdir(parents=True, exist_ok=True)
        for name, text in generated_files(L, by_id).items():
            p = d / name
            if not p.exists() or p.read_text(encoding="utf-8") != text:
                p.write_text(text, encoding="utf-8")
            written.append(p)
    return written


def main() -> int:
    files = build()
    for L in load_all():
        print(f"built lessons/{L.slug}/ ({len(L.steps)} steps)")
    print(f"{len(files)} files checked/written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
