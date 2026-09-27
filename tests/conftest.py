"""Shared pytest fixtures."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def bday_index() -> pd.DatetimeIndex:
    return pd.bdate_range("2020-01-01", periods=400)


@pytest.fixture
def random_frame(bday_index: pd.DatetimeIndex) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    n = len(bday_index)
    return pd.DataFrame(
        {
            "x": rng.normal(size=n).cumsum(),
            "y": np.exp(rng.normal(size=n) * 0.1) * 100,
        },
        index=bday_index,
    )
