<!-- GENERATED from site/content/lessons/03-lookahead-walkforward by `make lessons`: edit the source, not this file. -->
# Lesson 03: Look-ahead bias and walk-forward evaluation

⏱ **60 minutes** · Best on the website (Lessons → 03); offline: open `lesson.ipynb`, run top to bottom, answer each 🤔 first.

**You'll be able to:** show how a tiny look-ahead leak makes a useless forecast look brilliant; cut data at a forecast origin with `ForecastOrigin`; say which training rows a direct h-step model may use; prove a function is leak-free with the "scramble the future" test.

**You need:** Lesson 02 (or: you can index a pandas Series by date). (Prerequisites: Lesson 02.)

**Stuck on the checkpoint?** Hints, in order:

1. Row i's label covers rows i+1 … i+h. When is its *last* row already in the past?
2. It is usable when i + h ≤ origin_pos. Build all positions at once with `np.arange(n)`.
3. `np.arange(n) + h <= origin_pos` is already a boolean array of length n.

The full solution is `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| `TypeError: data must be indexed by a pandas DatetimeIndex` | Your index holds strings or integers. | `df.index = pd.to_datetime(df.index)`. |
| `ValueError: DatetimeIndex must be sorted ascending` | Rows are out of date order. | `df = df.sort_index()`. |
| `AssertionError: Look-ahead detected …` | Your function reads data after the origin. | Slice with `origin.history(data)` *first*, compute after. |
| Checker: row … should be True/False | Off by one in the availability rule. | Row i's label covers rows i+1 … i+h, so it needs i + h ≤ origin_pos. |

**Next:** Lesson 04 (AR, GARCH and HAR by hand).
