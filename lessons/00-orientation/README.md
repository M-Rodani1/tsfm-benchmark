<!-- GENERATED from site/content/lessons/00-orientation by `make lessons`: edit the source, not this file. -->
# Lesson 00: Orientation: how this project (and this site) work

⏱ **45 minutes** · Best on the website (Lessons → 00); offline: open `lesson.ipynb`, run top to bottom, answer each 🤔 first.

**You'll be able to:** say what runs in this browser and what runs on your own computer; find your way around the repository; read the pre-registered design from a config; use the lesson routine (predict, run, checkpoint, flashcards).

**You need:** Nothing. Start here. (Prerequisites: nothing.)

**Stuck on the checkpoint?** Hints, in order:

1. A primary test exists for every combination of TSFM, target and horizon.
2. The config has lists for each: `cfg.models.tsfms`, `cfg.targets.kinds`, `cfg.targets.horizons`.
3. Multiply their lengths: `len(a) * len(b) * len(c)`.

The full solution is `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| `make: command not found` (Windows) | No GNU make on this computer. | Use WSL, or type the command after `make`'s recipe by hand, e.g. `uv run tsfm-rc doctor`. |
| `ModuleNotFoundError: tsfm_rc` (in Jupyter) | The notebook kernel is not the project's environment. | Start Jupyter with `uv run jupyter lab` from the repository root. |
| `FileNotFoundError: … smoke …` | No stored results for the smoke run on this computer. | Run `make smoke` (about a minute). |
| `FAIL fixtures` in doctor | A fixture file was edited. | Restore it with `git checkout data/fixtures`. |

**Next:** Lesson 01 (Returns, log returns, and why they are hard to forecast).
