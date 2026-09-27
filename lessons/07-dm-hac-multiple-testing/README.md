# Lesson 07: Diebold–Mariano, HAC and multiple testing

⏱ **90 minutes** · Open `lesson.ipynb`, run top to bottom, answer each 🤔 first. Take a
break after section 3.

**You'll be able to:** run and hand-check a DM test, choose the HAC variance for overlapping
targets, control false discoveries with Holm, and read a Model Confidence Set.

**You need:** Lesson 06.

**Stuck on the checkpoint?** `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| `flag = 'zero_variance'` | d is constant (e.g. two identical models) | Check you are not comparing a model with itself |
| `flag = 'nonpositive_variance_…'` | Rectangular weights gave Ω ≤ 0 (rare, short samples) | Result is still computed with Bartlett; note the flag |
| p-value `nan` | Fewer than 3 paired observations | Check both models have forecasts on the same dates |
| Adjusted p-values > 1 | Forgot to cap at 1 in Holm | `min(1, …)` |
| MCS keeps every model | Losses too similar / sample too short | That is an honest answer: the data cannot separate them |

**Next:** Lesson 08 (contamination and how our test works).
