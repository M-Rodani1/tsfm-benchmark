<!-- GENERATED from site/content/lessons/05-foundation-models by `make lessons`: edit the source, not this file. -->
# Lesson 05: What a foundation model is, and how zero-shot forecasting works

⏱ **60 minutes** · Best on the website (Lessons → 05); offline: open `lesson.ipynb`, run top to bottom, answer each 🤔 first.

**You'll be able to:** explain "pretrained" and "zero-shot" for time series; show why scaling and patching let one model read any series; turn a model's quantiles into the study's forecasts (and why the median is wrong for variance); recognise an `UNAVAILABLE` model and what to do about it.

**You need:** Lessons 02–04. (Prerequisites: Lesson 02, Lesson 03, Lesson 04.)

**Stuck on the checkpoint?** Hints, in order:

1. For a normal X, q90 − q10 = 2 × 1.2816 × s. Solve for the standard deviation s.
2. The mean of exp(X) for a normal X with median (= mean) m is exp(m + s²/2).
3. `s = (q90 - q10) / (2 * 1.2815515655446004)`, then `return np.exp(median + s**2 / 2)`.

The full solution is `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| `UNAVAILABLE: python package … not installed` | The foundation-model packages (PyTorch) are not installed. In the browser they never are. | On your computer: `make install-tsfm` (downloads PyTorch, about 6 GB). |
| `UNAVAILABLE: could not download …` | No internet, a proxy or a firewall blocked Hugging Face. | Check the connection, then `make doctor ONLINE=1`. |
| Checker: "That is exp(median)" | You returned the median of exp(X), not its mean. | Add s²/2 inside the exp. |
| Checker: "Use s²/2, not s" | The lognormal mean uses half the *variance*. | `np.exp(median + s**2 / 2)`. |

**Next:** Lesson 06 (Loss functions, and why QLIKE for volatility).
