---
id: "00"
title: "Orientation: how this project (and this site) work"
minutes: 45
objectives:
  - say what runs in this browser and what runs on your own computer;
  - find your way around the repository;
  - read the pre-registered design from a config;
  - use the lesson routine (predict, run, checkpoint, flashcards).
prerequisites: []
you_need: "Nothing. Start here."
code_to_read: ["configs/default.yaml", "docs/PREREGISTRATION.md"]
mounts: ["fixtures", "configs", "results:smoke"]
next: "01"
---

## What runs where

This site is where you learn and where you follow the research. Lesson code runs **in this
browser tab** (Python compiled to WebAssembly, called Pyodide). Nothing is installed on your
computer, and your progress is saved as you go.

The foundation models and the full benchmark are far too heavy for a browser. They run on
your own computer from a terminal. The home page tells you exactly when a terminal task is
waiting, and which commands to type.

```predict
question: "Where does `make reproduce` (the full benchmark with the foundation models) run?"
options:
  - "In this browser tab"
  - "On your own computer, from a terminal"
  - "On the web server that hosts this site"
answer: 1
explain: "The site only *displays* stored results. Heavy experiments run locally; `make publish-results` exports their numbers and a push updates the site."
```

## Is the data what it should be?

On your computer, `make doctor` checks everything before a session and prints a fix for
each problem. Here is one of its checks, run on the files this page loaded. Every committed
fixture file must match its SHA-256 fingerprint.

```python
from tsfm_rc.pipeline.doctor import check_fixtures

c = check_fixtures()
print(c.status, "|", c.name, "|", c.detail)
```

## The map

```predict
question: "In which folder would you look for the code that computes the Diebold–Mariano test?"
options:
  - "results/"
  - "src/tsfm_rc/eval/"
  - "configs/"
  - "lessons/"
answer: 1
explain: "All statistics live in the package `src/tsfm_rc/`; the test itself is `src/tsfm_rc/eval/dm.py`."
```

```python
purpose = {
    "configs": "one YAML file per experiment (smoke, default, full)",
    "data": "fixtures (committed, synthetic) and raw/ (downloaded, never edited)",
    "docs": "pre-registration, decisions, glossary, pretraining data, build report",
    "lessons": "these lessons as Jupyter notebooks (an offline alternative)",
    "reports": "RESULTS.md, figures, offline dashboard (all generated)",
    "results": "stored forecasts and statistics (Parquet with provenance)",
    "site": "this website (lessons, results, review, progress)",
    "src": "the package tsfm_rc: data, models, engine, eval, reports",
    "tests": "automated checks (pytest), including the leakage tests",
}
for folder, what in purpose.items():
    print(f"{folder:8s} {what}")
```

## The design lives in a config

The *default* config is the pre-registered study. Nothing in it may change silently: every
change is a dated amendment in `docs/PREREGISTRATION.md`.

```python
from tsfm_rc.config import config_hash, load_config

cfg = load_config("configs/default.yaml")
print("assets:", len(cfg.data.tickers), "| horizons:", cfg.targets.horizons, "| stride:", cfg.evaluation.stride)
print("TSFMs:", [t.name for t in cfg.models.tsfms], "| context:", cfg.models.context_length)
print("config hash:", config_hash(cfg)[:16], "(stored next to every result)")
```

```predict
question: "How many *primary* tests does the pre-registration contain? (Every TSFM × every target × every horizon.)"
kind: number
answer: 27
tolerance: 0
explain: "3 models × 3 targets × 3 horizons = 27. That many tests is why lesson 07 needs a multiple-testing correction."
```

## Results are files, not screenshots

Every number on the Results page comes from a stored table with provenance. The lessons read
the same tables. These are from the `smoke` run on **synthetic** data, so they say nothing
about markets.

```python
from tsfm_rc.learn import stats_table

m = stats_table("smoke", "metrics")
print(m.query("ticker == 'POOLED' and period == 'full' and window == 'expanding' and target == 'rv' and horizon == 1")
      [["model", "qlike", "mse"]].round(3).to_string(index=False))
```

## How every lesson works, and your first checkpoint

- **Predict first**, then run: wrong predictions are where the learning happens.
- **Checkpoint**: write a small function; the checker answers ✅ or explains what is off.
  Hints come in tiers; the full solution is there after honest effort.
- **Flashcards** join your review queue when you finish the lesson.

Write `n_primary_tests(cfg)` returning the number of pre-registered primary tests, read
from the config (don't hard-code 27).

```checkpoint
```
