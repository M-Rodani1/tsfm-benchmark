<!-- GENERATED from site/content/lessons/02-volatility by `make lessons`: edit the source, not this file. -->
# Lesson 02: Volatility, and why range estimators work

⏱ **60 minutes** · Best on the website (Lessons → 02); offline: open `lesson.ipynb`, run top to bottom, answer each 🤔 first.

**You'll be able to:** explain why volatility is forecastable while returns are not; compute the Garman–Klass (GK) variance from open, high, low and close; show, against a known truth, that GK is a less noisy proxy than squared returns; explain the two caveats (discrete trading, the overnight gap).

**You need:** Lesson 01. (Prerequisites: Lesson 01.)

**Stuck on the checkpoint?** Hints, in order:

1. Translate the formula term by term: `0.5 · ln(H/L)²` minus `(2 ln 2 − 1) · ln(C/O)²`. NumPy's log is `np.log`.
2. The formula gives a variance of *decimal* log returns; the study works in percent, so multiply by 100² = 1e4.
3. `1e4 * (0.5 * np.log(h / l) ** 2 - (2 * np.log(2) - 1) * np.log(c / o) ** 2)`

The full solution is `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| Values 10,000× too small | The result is in decimal², not %². | Multiply by `1e4`. |
| `nan` or `RuntimeWarning` in `log` | Arguments swapped or a zero price. | Check the argument order `o, h, l, c`. |
| Negative GK values / wrong values | Wrong sign or constant on the `ln(C/O)` term. | It is `− (2*np.log(2) - 1) * np.log(c/o)**2`. |
| `KeyError: 'sigma2'` | Read the OHLCV file instead of the latent (truth) file. | Use `synthetic_latent.csv`. |

**Next:** Lesson 03 (Look-ahead bias and walk-forward evaluation).
