"""TSFM Reality Check: an honest benchmark of time-series foundation models on financial data.

Package layout (see README.md for the tour):

- ``config``       pydantic-validated YAML run configuration
- ``origin``       the ForecastOrigin abstraction: the ONLY way data is sliced for forecasting
- ``leakage``      generic "perturb the future" tests used across the test suite
- ``data``         providers, immutable raw cache, cleaning, targets, synthetic fixtures
- ``models``       the Forecaster interface, classical baselines and TSFM wrappers
- ``engine``       the walk-forward engine
- ``eval``         metrics, Diebold-Mariano, MCS, Holm, pooling, contamination, economics
- ``pipeline``     experiment runner, doctor, flashcards
- ``reports``      RESULTS.md, figures and the static dashboard
"""

__version__ = "0.1.0"
