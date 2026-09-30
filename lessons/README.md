# Lessons: learn to run and read this study yourself

Eleven sessions of 45–90 minutes. Each one teaches the *actual code* of this repository.

**The main way to take them is the website** (`site/`, see `docs/DEPLOY.md`): short steps,
Python in the browser, hints, saved progress and spaced-repetition review. The notebooks in
this folder are the offline alternative, generated from the same source
(`site/content/lessons/`).

| # | Lesson | Time | Builds on the code in |
|---|---|---|---|
| 00 | [Orientation](00-orientation/) | 45 min | configs, `make doctor`, `make smoke` |
| 01 | [Returns and why they're hard to forecast](01-returns/) | 60 min | `data/targets.py` |
| 02 | [Volatility and range estimators](02-volatility/) | 60 min | `data/targets.py`, `data/synthetic.py` |
| 03 | [Look-ahead bias and walk-forward](03-lookahead-walkforward/) | 60 min | `origin.py`, `leakage.py` |
| 04 | [AR, GARCH and HAR by hand](04-ar-garch-har/) | 90 min | `models/baselines.py` |
| 05 | [Foundation models, zero-shot](05-foundation-models/) | 60 min | `models/tsfm.py` |
| 06 | [Loss functions, QLIKE](06-loss-functions/) | 60 min | `eval/metrics.py` |
| 07 | [Diebold–Mariano, HAC, multiple testing](07-dm-hac-multiple-testing/) | 90 min | `eval/dm.py`, `multiple.py`, `mcs.py` |
| 08 | [Contamination and our test](08-contamination/) | 60 min | `contamination/`, `eval/contamination_test.py` |
| 09 | [Reading and critiquing results](09-reading-results/) | 60 min | `reports/`, `results/` |
| 10 | [Writing it up](10-writing-up/) | 90 min | `paper_template.md` |

## How every lesson works

1. **Start a session:** `make doctor` (it tells you what to fix, in plain English).
2. **Open the notebook:** `uv run jupyter lab` from the repo root (install once with
   `make install-all`), then `lessons/NN-…/lesson.ipynb`.
3. **🤔 Predict before you run.** Write your guess down; wrong guesses are the useful ones.
4. **Checkpoint:** a small function plus an auto-checker cell (✅ or a hint).
   `solution.py` exists; use it after 10 honest minutes.
5. **Common errors:** each lesson's README has a table of likely errors and fixes.
6. **Flashcards:** at the end of each notebook; `make flashcards` exports all of them to
   `flashcards.csv` for Anki (File → Import, Basic, comma-separated).
7. **Tick it off** in [`PROGRESS.md`](PROGRESS.md) and write one line you'd forget.

For maintainers: everything in `lessons/NN-…/` is **generated** from
`site/content/lessons/NN-…/` by `make lessons` (see `site/content/README.md`); edit the
source, never these files. CI checks the generated files are current, runs every lesson in a
browser-like sandbox and in a real browser, executes every notebook with its solution, and
checks that each checker rejects the unsolved starter.
