# Lesson 04: AR, GARCH and HAR by hand

⏱ **90 minutes** · Open `lesson.ipynb`, run top to bottom, answer each 🤔 first. Take a
break after section 2.

**You'll be able to:** fit AR by least squares with BIC, run the GARCH recursion, fit HAR,
and explain direct vs iterated forecasts, all checked against known true parameters.

**You need:** Lessons 01–03.

**Stuck on the checkpoint?** `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| `LinAlgError` / NaN coefficients | NaNs in the design matrix (rolling means start empty) | Keep only rows where `X.notna().all(axis=1)` |
| `ValueError: shapes not aligned` | Lag columns have different lengths | Slice every lag as `x[pmax - j : n_total - j]` |
| GARCH `ConvergenceWarning` | Optimiser struggled (short or odd sample) | Use ≥ 1000 observations; returns in percent |
| Your GARCH path explodes | Used `eps[t]` instead of `eps[t-1]`, or forgot `beta*s[t-1]` | Tomorrow depends on today's shock and today's variance |
| `KeyError: 'b_d'` | Looked at the GARCH spec | HAR parameters are under `SYN_HAR_A` |

**Next:** Lesson 05 (foundation models and zero-shot forecasting).
