# Lesson 06: Loss functions, and why QLIKE for volatility

⏱ **60 minutes** · Open `lesson.ipynb`, run top to bottom, answer each 🤔 first.

**You'll be able to:** match each loss to the forecast it rewards, show why a noisy proxy
breaks MAE but not QLIKE/MSE, and read an out-of-sample R².

**You need:** Lessons 02 and 04.

**Stuck on the checkpoint?** `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| `RuntimeWarning: divide by zero` / `nan` | A forecast of 0 or a negative variance | Variance forecasts must be > 0; the study never clips silently, it returns NaN |
| QLIKE values negative | Used `ln f + y/f` (un-normalised form) | Use `y/f − ln(y/f) − 1` |
| All three losses pick "A" | The noise you added is too small | Keep the gamma(4, 0.25) noise from the lesson |
| R² surprisingly negative | Normal for returns: estimating a mean adds noise | That is the point of section 4 |

**Next:** Lesson 07 (Diebold–Mariano, HAC and multiple testing).
