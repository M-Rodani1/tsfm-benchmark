# Lesson 02: Volatility and range estimators

⏱ **60 minutes** · Open `lesson.ipynb`, run top to bottom, answer each 🤔 first.

**You'll be able to:** compute Garman–Klass variance, grade volatility proxies against a
known truth, and name the estimator's two caveats.

**You need:** Lesson 01.

**Stuck on the checkpoint?** `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| Values 10,000× too small | Result in decimal², not %² | Multiply by `1e4` |
| `nan` or `RuntimeWarning` in `log` | Arguments swapped (`l/h` < 1 is fine, but a 0 price is not) | Check argument order `o, h, l, c` |
| Negative GK values | Wrong sign/constant on the `ln(C/O)` term | It is `− (2*np.log(2) - 1) * np.log(c/o)**2` |
| Plot is a flat line | Forgot `logy=True`; spikes dwarf the rest | Keep the log scale |
| `KeyError: 'sigma2'` | Read the OHLCV file instead of the latent file | Use `synthetic_latent.csv` |

**Next:** Lesson 03 (look-ahead bias and walk-forward evaluation).
