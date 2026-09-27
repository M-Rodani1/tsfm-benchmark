# Lesson 00: Orientation

⏱ **45 minutes** · Open `lesson.ipynb`, run top to bottom, answer each 🤔 first.

**You'll be able to:** check your setup, run the pipeline, find your way around, read the
pre-registered design, and use the lesson routine.

**You need:** nothing. Setup: `make install-all`, then `uv run jupyter lab` from the repo root.

**Stuck on the checkpoint?** `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| `make: command not found` (Windows) | No GNU make | Use WSL, or run the command after `make`'s `##` line by hand, e.g. `uv run tsfm-rc doctor` |
| `ModuleNotFoundError: tsfm_rc` | Notebook kernel is not the project's environment | Start Jupyter with `uv run jupyter lab` |
| `FileNotFoundError: …results/smoke…` | No stored results | `make smoke` |
| `✗ FAIL fixtures` in doctor | A fixture file was edited | `git checkout data/fixtures` |

**Next:** Lesson 01 (returns).
