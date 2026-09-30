<!-- GENERATED from site/content/lessons/09-reading-results by `make lessons`: edit the source, not this file. -->
# Lesson 09: Reading, and critiquing, our own results

⏱ **60 minutes** · Best on the website (Lessons → 09); offline: open `lesson.ipynb`, run top to bottom, answer each 🤔 first.

**You'll be able to:** trace any number in the report back to the stored table it came from; tell a *surviving* finding from one that only looked significant before correction; tell an *absent* result from a *null* result; run a critique checklist on any forecasting study, starting with this one.

**You need:** Lessons 06–08. (Prerequisites: Lesson 06, Lesson 07, Lesson 08.)

**Stuck on the checkpoint?** Hints, in order:

1. Only the *Holm-adjusted* p-value decides whether there is a finding at all.
2. If `p_holm <= alpha`, the sign of `mean_diff` decides the direction: negative means the model's loss is lower.
3. `if p_holm <= alpha: return "model better" if mean_diff < 0 else "model worse"`, otherwise `"no detectable difference"`.

The full solution is `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| `FileNotFoundError: … smoke …` | No stored results on this computer. | `make smoke` (about a minute). |
| `UndefinedVariableError` in `.query(...)` | A column name typo inside the query string. | `dm_all.columns` lists the real names. |
| Checker: "significant only BEFORE correction" | Your verdict used the raw p-value. | Use `p_holm`. |
| Checker: "Check the sign" | Better and worse are swapped. | Negative `mean_diff` = lower loss = model better. |

**Next:** Lesson 10 (Writing it up as a short paper).
