# Lesson 05: Foundation models and zero-shot forecasting

⏱ **60 minutes** · Open `lesson.ipynb`, run top to bottom, answer each 🤔 first.

**You'll be able to:** explain pretraining and zero-shot use, see scaling and patching,
convert quantile forecasts into the study's targets, and handle an unavailable model.

**You need:** Lessons 02–04. Real weights are optional (`make install-tsfm`, network).

**Stuck on the checkpoint?** `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| `UNAVAILABLE: python package … not installed` | TSFM extra missing | `make install-tsfm` (downloads PyTorch, ~6 GB) |
| `UNAVAILABLE: could not download …` | No internet / proxy / firewall | Check the connection, then `uv run huggingface-cli download amazon/chronos-bolt-tiny` |
| Very slow first run | Weights downloading, PyTorch warming up | Wait; the next run uses the local cache |
| `RuntimeError: … out of memory` | Batch too large for your RAM | Lower `batch_size` for that model in the config |
| Shapes like `(1, 20, 9)` confuse you | Batch × steps × quantiles | Take `[0]` for the first series, `[..., 4]` for the median |

**Next:** Lesson 06 (loss functions, and why QLIKE for volatility).
