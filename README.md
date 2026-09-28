# TSFM Reality Check

An honest, reproducible benchmark of pretrained **time-series foundation models**
(Chronos-Bolt, TimesFM 2.5, Moirai 1.1) against **strong classical baselines** (AR, GARCH,
GJR-GARCH, HAR, EWMA, LightGBM, naive rules) on daily **returns**, **realised volatility** and
**trading volume** of 26 US ETFs and large caps, with strict walk-forward evaluation,
Diebold–Mariano tests with HAC variance, multiple-testing control, a Model Confidence Set,
and an explicit **pretraining-contamination** test. Plus a **website** with eleven lessons
(Python runs in your browser), the results dashboard, spaced-repetition review and synced
progress, so the terminal is only needed for the heavy experiments.

> **Status of the numbers in this repository.** The environment this was built in could not
> reach Yahoo Finance or Hugging Face. Every committed result is therefore computed on
> **synthetic fixtures**, and all three foundation models are reported **UNAVAILABLE**.
> Nothing here is a finding about real markets yet. Run `make reproduce` on your machine to
> produce the real study (instructions below). See [`docs/BUILD-REPORT.md`](docs/BUILD-REPORT.md).

## The website (learning + results)

`site/` is the main way in: lessons in short steps with Python in the browser, the results
dashboard, flashcard review, notes and a session log, and a research-status page that tells
you when a terminal task is waiting. Deploy it with Netlify and Supabase by following
[`docs/DEPLOY.md`](docs/DEPLOY.md), or run it locally:

```bash
cd site && npm ci && npm run dev      # http://localhost:5173 (Node 22)
```

After a real run, `make publish-results` exports the stored numbers to `site/public/data/`;
commit and push, and the site shows them (fixture results are labelled
"SYNTHETIC — not research results").

## 10-minute quickstart (terminal)

You need `git`, `make` and [uv](https://docs.astral.sh/uv/getting-started/installation/)
(`curl -LsSf https://astral.sh/uv/install.sh | sh`). Everything else is installed by uv.

```bash
git clone <this repository> tsfm-reality-check && cd tsfm-reality-check
uv python install 3.11          # 1 min, only once
make install                    # 1-2 min: core + dev packages from uv.lock (no PyTorch)
make doctor                     # checks everything and tells you how to fix problems
make smoke                      # ~1 min: full pipeline on synthetic fixtures, offline
```

Then open:

- `reports/RESULTS.md`: the auto-generated report (tables, figures, plain-English findings,
  what survives multiple-testing correction, limitations, provenance);
- `reports/dashboard/index.html`: the interactive dashboard (double-click it; no server);
- `lessons/README.md`: the same lessons as notebooks, offline (`make install-all`, then `uv run jupyter lab`).

## Running the real study

```bash
make install-tsfm                                   # adds PyTorch + chronos/timesfm/uni2ts (~6 GB)
make fetch-data CONFIG=configs/default.yaml         # Yahoo Finance -> data/raw (immutable, hashed)
make reproduce                                      # data -> forecasts -> stats -> report -> dashboard
```

`make reproduce` downloads the three model checkpoints from Hugging Face on first use
(tens to hundreds of MB), then runs the pre-registered design. Expected runtime on a 4-core
laptop CPU: roughly 15 minutes for the baselines (extrapolated from the fixture run) plus
roughly 30–60 minutes for the foundation models. Neither has been timed on real data (see
the build report). Reruns reuse the forecast cache.
If Yahoo blocks you, put Yahoo-format CSVs in a folder and set `provider: csv` and
`csv_dir:` in a copy of the config (see `docs/DECISIONS.md` D-022).

## What is where

| Path | Contents |
|---|---|
| `docs/PREREGISTRATION.md` | The analysis plan, fixed before any result, with dated amendments A1–A4 |
| `docs/DECISIONS.md` | Every judgment call and why |
| `docs/PRETRAINING-DATA.md` | What each TSFM was trained on, with verification tags |
| `docs/GLOSSARY.md` | Short definitions of every term |
| `docs/BUILD-REPORT.md` | What was built, what was run, known weaknesses, next commands |
| `docs/DEFINITION-OF-DONE.md` | The acceptance checklist and its status |
| `configs/` | `smoke`, `smoke_real`, `default` (pre-registered), `default_fixtures`, `full` |
| `src/tsfm_rc/` | The package: `origin.py` (no look-ahead), `data/`, `models/`, `engine/`, `eval/`, `contamination/`, `reports/` |
| `tests/` | pytest suite, including leakage tests with negative controls |
| `results/<run>/` | Stored forecasts and statistics (Parquet with provenance) |
| `reports/` | `RESULTS.md`, figures and the dashboard, generated from `results/` |
| `site/` | The website: `content/` (lesson source), `src/` (app), `supabase/` (schema + RLS), tests |
| `lessons/` | The same lessons as Jupyter notebooks, generated from `site/content` by `make lessons` |
| `docs/DEPLOY.md` | Click-by-click deployment (Supabase, Netlify, DNS) |

## Make targets

`make help` lists them all. The main ones: `install`, `install-tsfm`, `install-all`, `test`,
`lint`, `doctor`, `smoke`, `fetch-data`, `reproduce`, `reproduce-fixtures`, `report`,
`dashboard`, `flashcards`, `lessons`, `publish-results`, `site`, `site-test`.

## Principles

No look-ahead (one `ForecastOrigin` slicing point, future-perturbation tests); no fabricated
numbers (every reported number is rendered from a stored artifact with SHA-256 and
provenance; unavailable models are marked UNAVAILABLE); Python is the only place numbers are
computed; one locked environment (`uv.lock`); seeds everywhere; a null result is a valid result.
