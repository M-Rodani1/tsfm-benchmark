<!-- GENERATED from site/content/lessons/04-ar-garch-har by `make lessons`: edit the source, not this file. -->
# Lesson 04: AR, GARCH and HAR by hand

⏱ **90 minutes** · Best on the website (Lessons → 04); offline: open `lesson.ipynb`, run top to bottom, answer each 🤔 first.

**You'll be able to:** fit AR(p) with least squares and pick p with BIC; run the GARCH(1,1) variance recursion yourself and recover the true parameters; build HAR regressors and explain why fitted coefficients look "too small"; tell a *direct* forecast from an *iterated* one.

**You need:** Lessons 01–03. (Prerequisites: Lesson 01, Lesson 02, Lesson 03.)

**Stuck on the checkpoint?** Hints, in order:

1. Create an empty array of the same length as `eps` and set its first element to `s0`.
2. Loop `for t in range(1, len(eps))`: each value needs the *previous* variance and the *previous* shock.
3. `s[t] = omega + alpha * eps[t - 1] ** 2 + beta * s[t - 1]`, then `return s`.

The full solution is `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| `LinAlgError` / NaN coefficients | NaNs in the design matrix (rolling means start empty). | Keep only rows where `X.notna().all(axis=1)`. |
| `ValueError: shapes not aligned` | Lag columns have different lengths. | Slice every lag as `x[pmax - j : n_total - j]`. |
| Your GARCH path is wrong or explodes | Used `eps[t]` instead of `eps[t-1]`, or `s0` instead of `s[t-1]`. | Tomorrow depends on today's shock and today's variance. |
| `KeyError: 'b_d'` | Looked at the GARCH spec. | HAR parameters are under `SYN_HAR_A`. |

**Next:** Lesson 05 (What a foundation model is, and how zero-shot forecasting works).
