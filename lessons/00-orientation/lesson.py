# %% [markdown]
# # Lesson 00: Orientation: how this project (and these lessons) work
# ⏱ **45 min** · code you will read: `configs/default.yaml`, `docs/PREREGISTRATION.md`
#
# **You'll be able to…**
# 1. check your setup with `make doctor` and run the pipeline with `make smoke`;
# 2. find your way around the repository;
# 3. read the pre-registered design from a config;
# 4. use the lesson routine: predict → run → checkpoint → flashcards → tick PROGRESS.md.
#
# **You need:** nothing. Start here.

# %% [markdown]
# ## 1. Before every session (2 minutes)
# In a terminal at the repo root:
# ```
# make doctor      # ✓ = fine, ! = optional, ✗ = fix it (the → line says how)
# make smoke       # whole pipeline on synthetic data, about a minute
# ```
# The same checks, from Python:

# %%
from tsfm_rc.pipeline.doctor import check_fixtures, check_python

for c in (check_python(), check_fixtures()):
    print(c.status, c.name, "-", c.detail)

# %% [markdown]
# ## 2. The map
# 🤔 **Predict before you run:** in which folder would you look for the code that computes
# the Diebold–Mariano test?

# %%
from tsfm_rc.paths import ROOT

purpose = {
    "configs": "one YAML file per experiment (smoke, default, full)",
    "data": "fixtures (committed, synthetic) and raw/ (downloaded, never edited)",
    "docs": "pre-registration, decisions, glossary, pretraining data, build report",
    "lessons": "you are here",
    "reports": "RESULTS.md, figures, dashboard (all generated)",
    "results": "stored forecasts and statistics (Parquet with provenance)",
    "src": "the package tsfm_rc: data, models, engine, eval, reports",
    "tests": "automated checks (pytest), including the leakage tests",
}
for d in sorted(p.name for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith(".")):
    print(f"{d:10s} {purpose.get(d, '')}")

# %% [markdown]
# (Answer: `src/tsfm_rc/eval/dm.py`.)
#
# ## 3. The design lives in a config
# The *default* config is the pre-registered study. Nothing about it may change silently.

# %%
from tsfm_rc.config import config_hash, load_config

cfg = load_config("configs/default.yaml")
print("assets:", len(cfg.data.tickers), "| horizons:", cfg.targets.horizons, "| stride:", cfg.evaluation.stride)
print("TSFMs:", [t.name for t in cfg.models.tsfms], "| context:", cfg.models.context_length)
print("config hash:", config_hash(cfg)[:16], "(stored next to every result)")

# %% [markdown]
# 🤔 **Predict:** how many *primary* tests does the pre-registration contain? (Hint: every
# TSFM × every target × every horizon.)
#
# ## 4. Results are files, not screenshots
# Every number in the report comes from a stored table. Here is one:

# %%
import pandas as pd

from tsfm_rc.paths import RESULTS_DIR

m = pd.read_parquet(RESULTS_DIR / "smoke" / "stats" / "metrics.parquet")
print(m.query("ticker == 'POOLED' and period == 'full' and window == 'expanding' and target == 'rv' and horizon == 1")
      [["model", "qlike", "mse"]].round(3).to_string(index=False))

# %% [markdown]
# ## 5. How each lesson works
# - **🤔 Predict** first, then run: wrong predictions are where learning happens.
# - **Checkpoint**: write a small function; the checker says ✅ or gives a hint. Stuck for
#   10 minutes? Open `solution.py`.
# - **Flashcards** at the end; `make flashcards` exports all of them to Anki.
# - Tick the lesson in `lessons/PROGRESS.md` and write one line you'd forget.
#
# ## ✅ Checkpoint
# Write `n_primary_tests(cfg)` returning the number of pre-registered primary tests.

# %% tags=["exercise"]
def n_primary_tests(cfg):
    # YOUR CODE HERE
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(n_primary_tests)

# %% [markdown] tags=["after-flashcards"]
# **Next:** open `lessons/01-returns/lesson.ipynb` (returns, and why they are hard to
# forecast). Tick lesson 00 in `lessons/PROGRESS.md`.
