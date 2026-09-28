# GENERATED from site/content/lessons/00-orientation by `make lessons`: edit the source, not this file.

# %% [markdown]
# # Lesson 00: Orientation: how this project (and this site) work
# ⏱ **45 min** · code you will read: `configs/default.yaml`, `docs/PREREGISTRATION.md`
#
# **You'll be able to…**
# 1. say what runs in this browser and what runs on your own computer;
# 2. find your way around the repository;
# 3. read the pre-registered design from a config;
# 4. use the lesson routine (predict, run, checkpoint, flashcards).
#
# **You need:** Nothing. Start here.

# %% [markdown]
# ## What runs where
#
# This site is where you learn and where you follow the research. Lesson code runs **in this
# browser tab** (Python compiled to WebAssembly, called Pyodide). Nothing is installed on your
# computer, and your progress is saved as you go.
#
# The foundation models and the full benchmark are far too heavy for a browser. They run on
# your own computer from a terminal. The home page tells you exactly when a terminal task is
# waiting, and which commands to type.
#
# 🤔 **Predict before you run:** Where does `make reproduce` (the full benchmark with the foundation models) run?
#
# - In this browser tab
# - On your own computer, from a terminal
# - On the web server that hosts this site
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **On your own computer, from a terminal.** The site only *displays* stored results. Heavy experiments run locally; `make publish-results` exports their numbers and a push updates the site.
#
# </details>

# %% [markdown]
# ## Is the data what it should be?
#
# On your computer, `make doctor` checks everything before a session and prints a fix for
# each problem. Here is one of its checks, run on the files this page loaded. Every committed
# fixture file must match its SHA-256 fingerprint.

# %%
from tsfm_rc.pipeline.doctor import check_fixtures

c = check_fixtures()
print(c.status, "|", c.name, "|", c.detail)

# %% [markdown]
# ## The map
#
# 🤔 **Predict before you run:** In which folder would you look for the code that computes the Diebold–Mariano test?
#
# - results/
# - src/tsfm_rc/eval/
# - configs/
# - lessons/
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **src/tsfm_rc/eval/.** All statistics live in the package `src/tsfm_rc/`; the test itself is `src/tsfm_rc/eval/dm.py`.
#
# </details>

# %%
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

# %% [markdown]
# ## The design lives in a config
#
# The *default* config is the pre-registered study. Nothing in it may change silently: every
# change is a dated amendment in `docs/PREREGISTRATION.md`.

# %%
from tsfm_rc.config import config_hash, load_config

cfg = load_config("configs/default.yaml")
print("assets:", len(cfg.data.tickers), "| horizons:", cfg.targets.horizons, "| stride:", cfg.evaluation.stride)
print("TSFMs:", [t.name for t in cfg.models.tsfms], "| context:", cfg.models.context_length)
print("config hash:", config_hash(cfg)[:16], "(stored next to every result)")

# %% [markdown]
# 🤔 **Predict before you run:** How many *primary* tests does the pre-registration contain? (Every TSFM × every target × every horizon.)
#
# <details><summary>Answer (after you have predicted)</summary>
#
# **27.** 3 models × 3 targets × 3 horizons = 27. That many tests is why lesson 07 needs a multiple-testing correction.
#
# </details>

# %% [markdown]
# ## Results are files, not screenshots
#
# Every number on the Results page comes from a stored table with provenance. The lessons read
# the same tables. These are from the `smoke` run on **synthetic** data, so they say nothing
# about markets.

# %%
from tsfm_rc.learn import stats_table

m = stats_table("smoke", "metrics")
print(m.query("ticker == 'POOLED' and period == 'full' and window == 'expanding' and target == 'rv' and horizon == 1")
      [["model", "qlike", "mse"]].round(3).to_string(index=False))

# %% [markdown]
# ## How every lesson works, and your first checkpoint
#
# - **Predict first**, then run: wrong predictions are where the learning happens.
# - **Checkpoint**: write a small function; the checker answers ✅ or explains what is off.
#   Hints come in tiers; the full solution is there after honest effort.
# - **Flashcards** join your review queue when you finish the lesson.
#
# Write `n_primary_tests(cfg)` returning the number of pre-registered primary tests, read
# from the config (don't hard-code 27).

# %% tags=["exercise"]
def n_primary_tests(cfg):
    # YOUR CODE HERE
    raise NotImplementedError

# %% tags=["checker"]
from checker import check
check(n_primary_tests)

# %% [markdown] tags=["flashcards"]
# ## Flashcards
#
# Cover the answer, say it out loud, then check. `make flashcards` exports these to Anki; the website schedules them for review.
#
# 1. **Q:** What should you run at the start of every session?
#    - **A:** make doctor (checks setup and prints fixes), then make smoke if you changed code.
# 2. **Q:** What does make smoke do?
#    - **A:** Runs the whole pipeline (data, forecasts, statistics, report, dashboard) on committed synthetic fixtures, offline, in about a minute.
# 3. **Q:** Where is the analysis plan written down before any result?
#    - **A:** docs/PREREGISTRATION.md (changes only as dated amendments).
# 4. **Q:** Where are judgment calls explained?
#    - **A:** docs/DECISIONS.md, one numbered entry per decision.
# 5. **Q:** Where do the numbers in reports/RESULTS.md come from?
#    - **A:** Stored tables in results/<run>/stats/*.parquet, each carrying provenance.
# 6. **Q:** How many primary tests does the study have, and why?
#    - **A:** 27 = 3 TSFMs × 3 targets × 3 horizons.
# 7. **Q:** What runs in the browser, and what needs a terminal?
#    - **A:** Lessons and result pages run in the browser; the full benchmark and the foundation models run locally from a terminal (make reproduce).
# 8. **Q:** How do new results reach the website?
#    - **A:** make publish-results exports the stored statistics to versioned JSON in site/public/data; commit and push, and the site rebuilds.

# %% [markdown] tags=["after-flashcards"]
# **Next:** open `lessons/01-returns/lesson.ipynb` (Returns, log returns, and why they are hard to forecast). Tick lesson 00 in `lessons/PROGRESS.md`.
