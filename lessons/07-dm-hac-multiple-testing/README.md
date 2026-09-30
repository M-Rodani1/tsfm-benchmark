<!-- GENERATED from site/content/lessons/07-dm-hac-multiple-testing by `make lessons`: edit the source, not this file. -->
# Lesson 07: Diebold–Mariano, HAC, and the multiple-testing problem

⏱ **90 minutes** · Best on the website (Lessons → 07); offline: open `lesson.ipynb`, run top to bottom, answer each 🤔 first.

**You'll be able to:** test whether two forecasts differ in expected loss (Diebold–Mariano); explain why overlapping 20-day targets need a HAC variance, and pick the right one; explain why 27 tests at 5% almost guarantee a false "discovery", and fix it with Holm; read a Model Confidence Set.

**You need:** Lesson 06. (Prerequisites: Lesson 06.)

**Stuck on the checkpoint?** Hints, in order:

1. Sort the p-values (`np.argsort(p)`). The k-th smallest (k = 0, 1, …) is multiplied by m − k.
2. Cap each value at 1, and keep a running maximum along the sorted order so adjusted values never go down.
3. Loop over `order = np.argsort(p)` with its rank; `running = max(running, min(1, (m - rank) * p[i]))`; store it at position i.

The full solution is `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| `flag = 'zero_variance'` | d is constant (e.g. two identical models). | Check you are not comparing a model with itself. |
| Checker: "That is Bonferroni" | Every p-value was multiplied by m. | Holm multiplies the k-th smallest by (m − k), k = 0, 1, … |
| Checker: "Cap adjusted p-values at 1" | Some adjusted values exceed 1. | `min(1, …)`. |
| Checker: "running maximum" | Adjusted values decrease somewhere along the sorted order. | Keep `running = max(running, …)`. |

**Next:** Lesson 08 (Contamination, and how our test works).
