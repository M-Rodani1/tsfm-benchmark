# Lesson content: the single source

Everything a learner sees in a lesson lives here, as plain Markdown, YAML and Python, so a
later audit can read and edit it without touching application code. The website builds from
these files, and `make lessons` regenerates the offline Jupyter track in `lessons/` from them.
Never edit `lessons/NN-…/` by hand.

```text
site/content/
  errors.yaml                 general plain-English explanations of Python errors
  lessons/NN-slug/
    lesson.md                 front matter + steps
    checkpoint/
      exercise.yaml           function name + 2–4 tiered hints
      starter.py              what the learner starts from (must fail the checker)
      solution.py             the reference solution (must pass the checker)
      checker.py              check(fn): raises AssertionError("❌ …") or prints "✅ …"
    flashcards.yaml           5–10 cards: - q: … / a: …
    errors.yaml               lesson-specific error explanations (also the README table)
    <assets>                  files the lesson opens (listed under `assets:`)
```

## `lesson.md`

````markdown
---
id: "04"                      # two digits, matches the folder prefix
title: "AR, GARCH and HAR by hand"
minutes: 90                   # 45–90, shown up front
objectives: [...]             # "You'll be able to…"
prerequisites: ["01", "02"]   # shown as locks on the site; the learner can override them
you_need: "Lessons 01–03."
code_to_read: ["src/tsfm_rc/models/baselines.py"]
mounts: ["fixtures"]          # data the browser loads: fixtures, configs, results:<run>
assets: []                    # files from this folder copied next to the lesson
browser_note: "…"             # optional: what differs in the browser, and why
next: "05"                    # the Next button (null for the last lesson)
---

## Step title                 <- every level-2 heading starts a step

At most 150 words of prose between two interactive elements.

```python                     <- runnable, editable code (autosaved as you type)
print("hello")
```

```predict                    <- "predict before you run"
question: "…"
options: ["…", "…"]           # multiple choice: answer = index; or kind: number with
answer: 1                     # answer + tolerance (+ unit); explain is shown afterwards
explain: "…"
```

```checkpoint                 <- the graded exercise (exactly one, in the last step)
```
````

Other fenced blocks (for example ```` ```text ````) are shown as-is and are not interactive.

## Rules (checked automatically)

`tests/test_lessons.py` and the site build (`site/scripts/build-content.mjs`) enforce:

- every step has at least one interactive element;
- at most **150 words** of prose between interactive elements, and about 600 words (hard
  limit 650) per lesson;
- 45–90 minutes, 2–4 hints, 5–10 flashcards, valid prerequisites and `next`;
- every `errors.yaml` entry has `see`, `match` (a regular expression tested against
  `"ErrorType: message"`), `why` and `fix`.

Each lesson is also executed in a browser-like Python sandbox: only the mounted files, and no
`arch`/`lightgbm`/`pyarrow`/`torch`. All cells must run, the solution must pass and the starter
must fail. In CI, Playwright runs every cell and every checkpoint in a real browser
(`site/e2e/exercises.spec.ts`).

## Runtime in the browser

The site runs Python with Pyodide in a Web Worker. It loads NumPy, pandas, SciPy, matplotlib,
pydantic and PyYAML, and checks at build time that each is in Pyodide's package list. It
installs a pure-Python wheel of `tsfm_rc` built from `src/` with `micropip` and mounts the
lesson's `mounts` at the paths `tsfm_rc.paths` expects. Where the study uses a package the
browser lacks, the lesson says so in `browser_note`, and uses either a tested NumPy
re-implementation (lesson 04: `tsfm_rc.models.garch_np`, checked against `arch`) or stored
results exported by `make publish-results` (lessons 00, 09, 10: `tsfm_rc.learn.stats_table`).

After editing, run `make lessons` (regenerates `lessons/`) and `make test`.
