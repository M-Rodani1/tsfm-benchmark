"""Feature builders (all strictly causal: the row for date s uses data <= s only).

Used by HAR (3 regressors) and LightGBM (16 features, PREREGISTRATION.md section 5.3).
Every rolling window is trailing; nothing is centred and nothing is shifted backwards.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsfm_rc.models.base import daily_target_series


def har_design(x: pd.Series) -> pd.DataFrame:
    """HAR regressors at each date s: x_s, mean(x_{s-4..s}), mean(x_{s-21..s})."""
    return pd.DataFrame(
        {
            "d": x,
            "w": x.rolling(5, min_periods=5).mean(),
            "m": x.rolling(22, min_periods=22).mean(),
        },
        index=x.index,
    )


def lgbm_features(history: pd.DataFrame, kind: str) -> pd.DataFrame:
    x = daily_target_series(history, kind)
    lg = history["log_gk_in"]
    lv = history["logvol_in"]
    f = {}
    for k in range(5):  # lags 1..5 in forecasting terms = values at s, s-1, ..., s-4
        f[f"x_lag{k + 1}"] = x.shift(k)
    f["x_mean5"] = x.rolling(5, min_periods=5).mean()
    f["x_mean22"] = x.rolling(22, min_periods=22).mean()
    f["r"] = history["r"]
    f["abs_r"] = history["r"].abs()
    f["lgk_1"] = lg
    f["lgk_5"] = lg.rolling(5, min_periods=5).mean()
    f["lgk_22"] = lg.rolling(22, min_periods=22).mean()
    f["lv_1"] = lv
    f["lv_5"] = lv.rolling(5, min_periods=5).mean()
    f["lv_22"] = lv.rolling(22, min_periods=22).mean()
    f["dow"] = history["dow"].astype(float)
    out = pd.DataFrame(f, index=history.index)
    return out.replace([np.inf, -np.inf], np.nan)
