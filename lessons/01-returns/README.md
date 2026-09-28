<!-- GENERATED from site/content/lessons/01-returns by `make lessons`: edit the source, not this file. -->
# Lesson 01: Returns, log returns, and why they are hard to forecast

⏱ **60 minutes** · Best on the website (Lessons → 01); offline: open `lesson.ipynb`, run top to bottom, answer each 🤔 first.

**You'll be able to:** compute simple and log returns and say why we use log returns; build the h-step return target exactly as the study does; show that returns barely autocorrelate but their *size* does; estimate how many years of data you need to even detect an average return.

**You need:** Basic Python and pandas (`df["col"]`, `.loc`). The data are committed synthetic fixtures. (Prerequisites: Lesson 00.)

**Stuck on the checkpoint?** Hints, in order:

1. An h-day log return is the log of a price ratio: which two prices?
2. The price at the origin row `i`, and the price h rows later, `prices[i + h]`.
3. Returns are in percent: multiply the log ratio by 100.

The full solution is `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| `ProviderError: SYN_X: not in fixture` | Ticker name typo. | Use one of `SYN_GARCH_A`, `SYN_GARCH_B`, `SYN_HAR_A`, `SYN_HAR_B`, `SYN_QUIRKS`. |
| `RuntimeWarning: divide by zero in log` | A price of 0 or a missing value. | Check `prices.min() > 0`; drop NaNs first. |
| Your number is 100× too small | The study's returns are in percent. | Multiply by 100. |
| Off by one day | Used the wrong pair of rows. | The target runs from row i to row i + h (its daily returns are rows i+1 … i+h). |
| `IndexError` | `i + h` is past the end of the array. | Choose `i < len(prices) - h`. |

**Next:** Lesson 02 (Volatility, and why range estimators work).
