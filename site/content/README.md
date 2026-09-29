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
figure: vol-clusters          # optional, a chart question: figures/<name>.json (one path per
                              # option), written by `make lessons` from tsfm_rc.learn; the build
                              # fails if `answer` differs from the figure's computed answer
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

## The journey and terminal tasks

`journey.yaml` is the guided route through the whole project: the site's “Do this next”
card, the **Your path** page, the breadcrumbs and every “Next step” button are computed from
it (`src/lib/journey.ts`). It has the three welcome-tour screens and the phases P0–P7, in
order. Each phase has `id`, `title`, `goal` (one sentence), `why` (one or two sentences),
`time`, `steps` and `done`, and optionally `kind: terminal`, `note`, `requires` (phases that
must be done first; the phase shows as locked until then), `requires_real_results` and
`parallel_with`. A step is exactly one of `lesson: "NN"`, `task: <id>` or
`site: welcome | results | review` (with a `title`), and may be `optional: true`. Every lesson
and every task must appear exactly once.

`tasks/<id>.yaml` is one terminal task (a step done on your laptop). Each has a `title`, a
`why`, a `time`, an optional `note` and `before` list, and `commands`. Each command has a
`title` and one of:

- `run` (the same everywhere), or
- `run_os` with `macos` / `windows` / `linux` (Windows means inside WSL), or
- `text` (an instruction, not a command).

A command can be limited to some systems with `os: [windows]`, and can carry an `os_note`, an
`expect` (what you should see), a `time` and `errors`. An error is written in one of three
ways:

- `see` + `fix`;
- `doctor: <key>`, which reuses the doctor's own message from `doctor_fixes.json` (generated
  from `src/tsfm_rc/pipeline/doctor.py` by `make lessons`);
- `error: <start of a see>`, which reuses an entry of `errors.yaml`.

A task ends with a `check`:
- `parser` is `doctor`, `study`, `publish` or `tests`: the rules in `src/lib/cliparse.ts`,
  which read the pasted output;
- `prompt` and `success` say what to paste and what counts as success;
- optionally `auto: real_results` (done by itself once a real run is published) and
  `start_button` (for a task that runs for hours).

`scripts/journey.mjs` validates all of this at build time.
