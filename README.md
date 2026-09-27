# TSFM Reality Check

An honest, reproducible benchmark of pretrained time-series foundation models (Chronos-Bolt,
TimesFM, Moirai) against strong classical baselines on daily financial returns, realised
volatility and trading volume, plus a lesson track that teaches you to run it yourself.

> Work in progress: built in eight steps (see `git log`). The full quickstart arrives in Build 08.

- Design, fixed before any result: [`docs/PREREGISTRATION.md`](docs/PREREGISTRATION.md)
- Every judgment call: [`docs/DECISIONS.md`](docs/DECISIONS.md)
- Terms: [`docs/GLOSSARY.md`](docs/GLOSSARY.md)
- Lessons: [`lessons/`](lessons/) (tick them off in [`lessons/PROGRESS.md`](lessons/PROGRESS.md))

```bash
uv sync            # install locked core + dev dependencies (Python 3.11)
make test          # run the test suite
make smoke         # run the pipeline on committed synthetic fixtures
```
