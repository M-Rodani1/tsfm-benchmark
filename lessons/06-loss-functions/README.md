<!-- GENERATED from site/content/lessons/06-loss-functions by `make lessons`: edit the source, not this file. -->
# Lesson 06: Loss functions, and why QLIKE for volatility

⏱ **60 minutes** · Best on the website (Lessons → 06); offline: open `lesson.ipynb`, run top to bottom, answer each 🤔 first.

**You'll be able to:** say which forecast each loss rewards (mean, median, a quantile); show why a *noisy* volatility proxy breaks some losses but not QLIKE or MSE; explain QLIKE's asymmetry; read an out-of-sample R².

**You need:** Lessons 02 and 04. (Prerequisites: Lesson 02, Lesson 04.)

**Stuck on the checkpoint?** Hints, in order:

1. Everything depends on the ratio of truth to forecast: compute `ratio = y / f` first.
2. The loss is the ratio minus its log minus one; it must be exactly 0 when f = y.
3. `return ratio - np.log(ratio) - 1` (keep it y/f, not f/y).

The full solution is `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| `RuntimeWarning: divide by zero` / `nan` | A forecast of 0 or a negative variance. | Variance forecasts must be > 0; the study never clips silently, it returns NaN. |
| Checker: "un-normalised form" | Used `ln f + y/f`. | Use `y/f − ln(y/f) − 1`. |
| Checker: "Ratio upside down" | Computed f/y. | It is y/f (truth over forecast). |

**Next:** Lesson 07 (Diebold–Mariano, HAC, and the multiple-testing problem).
