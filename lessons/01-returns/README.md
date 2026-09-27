# Lesson 01: Returns and why they are hard to forecast

⏱ **60 minutes** · Open `lesson.ipynb`, run top to bottom, answer each 🤔 first.

**You'll be able to:** compute log returns and h-step targets, read an autocorrelation plot,
and explain why the zero forecast is hard to beat.

**You need:** basic Python and pandas. Start here.

**Stuck on the checkpoint?** `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| `ProviderError: SYN_X: not in fixture` | Ticker name typo | Use one of `SYN_GARCH_A`, `SYN_GARCH_B`, `SYN_HAR_A`, `SYN_HAR_B`, `SYN_QUIRKS` |
| `RuntimeWarning: divide by zero in log` | A price of 0 or a missing value | Check `prices.min() > 0`; drop NaNs first |
| Your number is 100× too small | Forgot the percent factor | Multiply by 100 |
| Off by one day | Used rows i…i+h-1 | The target starts at row i+1 |
| `IndexError` | `i + h` past the end of the array | Choose `i < len(prices) - h` |

**Next:** Lesson 02 (volatility and range estimators).
