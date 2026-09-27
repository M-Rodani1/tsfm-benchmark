# Lesson 03: Look-ahead bias and walk-forward evaluation

⏱ **60 minutes** · Open `lesson.ipynb` and run cells top to bottom.

**You'll be able to:** demonstrate a look-ahead leak, cut data with `ForecastOrigin`,
choose valid training rows for direct models, and test code for leaks.

**You need:** Lesson 02.

**Stuck on the checkpoint?** `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| `TypeError: data must be indexed by a pandas DatetimeIndex` | Your index holds strings or integers | `df.index = pd.to_datetime(df.index)` |
| `ValueError: DatetimeIndex must be sorted ascending` | Rows out of date order | `df = df.sort_index()` |
| `AssertionError: Look-ahead detected …` | Your function reads data after the origin | Slice with `origin.history(data)` *first*, compute after |
| `ModuleNotFoundError: tsfm_rc` or `checker` | Wrong kernel or working folder | Start Jupyter with `make install-all` then `uv run jupyter lab` from the repo root, open the notebook from its folder |
| `NotImplementedError` in the checker cell | You haven't written the exercise yet | Replace `raise NotImplementedError` with your code |

**Next:** Lesson 04 (AR, GARCH and HAR by hand).
