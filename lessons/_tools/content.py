"""Parser for the lesson source format in ``site/content/lessons/`` (the single source).

The website parses the same files at build time (``site/scripts/build-content.mjs``); the
Jupyter notebooks in ``lessons/`` are generated from them by ``build_notebooks.py``.
``tests/test_site_content.py`` checks that both parsers agree. The format is documented in
``site/content/README.md``:

    ---
    <YAML front matter: id, title, minutes, objectives, prerequisites, you_need, ...>
    ---
    ## Step title          <- every level-2 heading starts a step
    Some markdown prose (at most 150 words between two interactive elements).

    ```python              <- a runnable (editable) code cell
    print(1 + 1)
    ```

    ```predict             <- "predict before you run": YAML with question/options/answer
    question: ...
    ```

    ```checkpoint          <- where the graded checkpoint exercise sits (files in checkpoint/)
    ```
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONTENT_DIR = ROOT / "site" / "content"
LESSON_CONTENT_DIR = CONTENT_DIR / "lessons"
FENCE_OPEN = re.compile(r"^```([A-Za-z0-9_-]*)\s*$")
BLOCK_KINDS = {"python", "predict", "checkpoint"}
PROSE_LIMIT = 150  # words between two interactive elements
LESSON_PROSE_LIMIT = 650  # all prose of one lesson ("about 600 words")


@dataclass
class Block:
    kind: str  # "md" | "python" | "predict" | "checkpoint"
    text: str = ""
    data: dict = field(default_factory=dict)


@dataclass
class Step:
    id: str
    title: str
    blocks: list[Block]

    @property
    def activities(self) -> list[Block]:
        return [b for b in self.blocks if b.kind != "md"]


@dataclass
class Exercise:
    function: str
    hints: list[str]
    starter: str
    solution: str
    checker: str


@dataclass
class Lesson:
    dir: Path
    meta: dict
    steps: list[Step]
    exercise: Exercise
    flashcards: list[dict]
    errors: list[dict]

    @property
    def id(self) -> str:
        return str(self.meta["id"])

    @property
    def slug(self) -> str:
        return self.dir.name

    @property
    def title(self) -> str:
        return self.meta["title"]


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "step"


def words(text: str) -> int:
    """Words of prose: inline code counts as one word, markdown punctuation is ignored."""
    text = re.sub(r"`[^`]*`", " x ", text)
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-]*", text))


def split_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise ValueError("lesson.md must start with YAML front matter (---)")
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end]) or {}, text[end + 5 :]


def parse_body(body: str) -> tuple[str, list[tuple[str, list[Block]]]]:
    """Returns (text before the first step, [(step title, blocks)])."""
    intro: list[str] = []
    steps: list[tuple[str, list[Block]]] = []
    md: list[str] = []
    lines = body.splitlines()
    i = 0

    def flush():
        text = "\n".join(md).strip()
        md.clear()
        if text:
            if steps:
                steps[-1][1].append(Block("md", text))
            else:
                intro.append(text)

    while i < len(lines):
        line = lines[i]
        m = FENCE_OPEN.match(line)
        if m and m.group(1) in BLOCK_KINDS:
            kind = m.group(1)
            j = i + 1
            while j < len(lines) and lines[j].rstrip() != "```":
                j += 1
            if j == len(lines):
                raise ValueError(f"unclosed ``` {kind} block starting at line {i + 1}")
            content = "\n".join(lines[i + 1 : j])
            flush()
            if not steps:
                raise ValueError(f"``` {kind} block before the first step (## heading)")
            if kind == "predict":
                steps[-1][1].append(Block(kind, content, yaml.safe_load(content) or {}))
            else:
                steps[-1][1].append(Block(kind, content.rstrip("\n")))
            i = j + 1
            continue
        if m and m.group(1):  # other fenced blocks (e.g. ```text) stay part of the prose
            j = i + 1
            while j < len(lines) and lines[j].rstrip() != "```":
                j += 1
            md.extend(lines[i : j + 1])
            i = j + 1
            continue
        if line.startswith("## "):
            flush()
            steps.append((line[3:].strip(), []))
        else:
            md.append(line)
        i += 1
    flush()
    return "\n\n".join(intro), steps


def load_lesson(d: Path) -> Lesson:
    meta, body = split_front_matter((d / "lesson.md").read_text(encoding="utf-8"))
    intro, raw_steps = parse_body(body)
    if intro:
        raise ValueError(f"{d.name}: text before the first step; put it in the front matter or a step")
    steps = []
    for title, blocks in raw_steps:
        steps.append(Step(slugify(title), title, blocks))
    cp = d / "checkpoint"
    ex_meta = yaml.safe_load((cp / "exercise.yaml").read_text(encoding="utf-8"))
    exercise = Exercise(
        function=ex_meta["function"],
        hints=[str(h).strip() for h in ex_meta.get("hints", [])],
        starter=(cp / "starter.py").read_text(encoding="utf-8").rstrip("\n"),
        solution=(cp / "solution.py").read_text(encoding="utf-8").rstrip("\n"),
        checker=(cp / "checker.py").read_text(encoding="utf-8"),
    )
    cards = yaml.safe_load((d / "flashcards.yaml").read_text(encoding="utf-8")) or []
    errors = yaml.safe_load((d / "errors.yaml").read_text(encoding="utf-8")) or []
    return Lesson(d, meta, steps, exercise, cards, errors)


def lesson_dirs() -> list[Path]:
    return sorted(p for p in LESSON_CONTENT_DIR.iterdir() if p.is_dir() and re.match(r"^\d\d-", p.name))


def load_all() -> list[Lesson]:
    return [load_lesson(d) for d in lesson_dirs()]


def load_global_errors() -> list[dict]:
    return yaml.safe_load((CONTENT_DIR / "errors.yaml").read_text(encoding="utf-8")) or []


def prose_segments(step: Step) -> list[str]:
    """Prose between interactive elements (and before the first / after the last)."""
    segs, cur = [], []
    for b in step.blocks:
        if b.kind == "md":
            cur.append(b.text)
        else:
            segs.append("\n\n".join(cur))
            cur = []
    segs.append("\n\n".join(cur))
    return segs


def validate(lesson: Lesson, all_ids: set[str]) -> list[str]:
    """Problems with one lesson (empty list = fine). Mirrors the site's build-time checks."""
    p: list[str] = []
    m = lesson.meta
    for key in ("id", "title", "minutes", "objectives", "prerequisites", "you_need", "next"):
        if key not in m:
            p.append(f"front matter lacks '{key}'")
    if not 45 <= int(m.get("minutes", 0)) <= 90:
        p.append("a lesson must fit a 45-90 minute session")
    if not lesson.slug.startswith(str(m.get("id", "")) + "-"):
        p.append(f"folder {lesson.slug} does not start with id {m.get('id')}")
    for pre in m.get("prerequisites") or []:
        if pre not in all_ids:
            p.append(f"unknown prerequisite {pre}")
    nxt = m.get("next")
    if nxt is not None and nxt not in all_ids:
        p.append(f"unknown next lesson {nxt}")
    ids = [s.id for s in lesson.steps]
    if len(set(ids)) != len(ids):
        p.append("duplicate step titles")
    total = 0
    n_checkpoints = 0
    for s in lesson.steps:
        if not s.activities:
            p.append(f"step '{s.title}' has nothing to do (needs a python, predict or checkpoint block)")
        for seg in prose_segments(s):
            n = words(seg)
            total += n
            if n > PROSE_LIMIT:
                p.append(f"step '{s.title}': {n} words between interactive elements (limit {PROSE_LIMIT})")
        for b in s.activities:
            if b.kind == "predict":
                q = b.data
                if "question" not in q or "explain" not in q:
                    p.append(f"step '{s.title}': predict needs 'question' and 'explain'")
                if "options" in q and not (isinstance(q.get("answer"), int) and 0 <= q["answer"] < len(q["options"])):
                    p.append(f"step '{s.title}': predict 'answer' must index 'options'")
            if b.kind == "checkpoint":
                n_checkpoints += 1
    if n_checkpoints != 1 or (lesson.steps and not any(b.kind == "checkpoint" for b in lesson.steps[-1].blocks)):
        p.append("exactly one checkpoint, in the last step")
    if total > LESSON_PROSE_LIMIT:
        p.append(f"{total} words of prose in total (limit {LESSON_PROSE_LIMIT})")
    if not 5 <= len(lesson.flashcards) <= 10:
        p.append(f"need 5-10 flashcards, found {len(lesson.flashcards)}")
    if any(set(c) != {"q", "a"} for c in lesson.flashcards):
        p.append("each flashcard needs exactly 'q' and 'a'")
    if not 2 <= len(lesson.exercise.hints) <= 4:
        p.append("checkpoint needs 2-4 tiered hints")
    for e in lesson.errors:
        if not {"see", "match", "why", "fix"} <= set(e):
            p.append(f"errors.yaml entry lacks see/match/why/fix: {e}")
        else:
            try:
                re.compile(e["match"])
            except re.error as err:
                p.append(f"bad regex {e['match']!r}: {err}")
    return p
