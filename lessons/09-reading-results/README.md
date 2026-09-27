# Lesson 09: Reading and critiquing our results

⏱ **60 minutes** · Open `lesson.ipynb`, run top to bottom, answer each 🤔 first. Keep
`reports/RESULTS.md` open in a second tab.

**You'll be able to:** trace report numbers to stored tables, separate surviving findings
from multiplicity casualties, recognise absent results, and apply a critique checklist.

**You need:** Lessons 06–08, and results in `results/smoke/` (committed; `make smoke` rebuilds them).

**Stuck on the checkpoint?** `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| `FileNotFoundError: …/stats/dm_all.parquet` | No results yet | `make smoke` (takes about a minute) |
| `UndefinedVariableError` in `.query(...)` | Column name typo | `dm_all.columns` lists the real names |
| Your verdicts disagree with the report | Used the raw p-value | Use `p_holm` |
| Numbers differ from the report | You ran `make smoke` after opening the report | Reload `reports/smoke/RESULTS.md` |

**Next:** Lesson 10 (writing it up as a short paper).
