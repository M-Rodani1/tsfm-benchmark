"""Tests for the look-ahead detector itself, including NEGATIVE CONTROLS.

A leakage test that can never fail is worthless. These tests feed the detector
deliberately leaky functions (full-sample scaling, centred rolling windows, a
direct regression that uses unrealised labels, hyper-parameter selection on the
full sample) and check that every one of them is caught.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tsfm_rc.leakage import assert_future_invariant, is_future_invariant, perturb_future
from tsfm_rc.origin import ForecastOrigin


@pytest.fixture
def origin(random_frame):
    return ForecastOrigin(random_frame.index[250])


def test_perturb_future_leaves_past_untouched(random_frame, origin):
    p = perturb_future(random_frame, origin.timestamp, seed=3)
    past = random_frame.index <= origin.timestamp
    pd.testing.assert_frame_equal(p.loc[past], random_frame.loc[past])
    assert not np.allclose(p.loc[~past].to_numpy(), random_frame.loc[~past].to_numpy())
    # positive column stays positive (so leaky code does not crash on log())
    assert (p["y"] > 0).all()


def test_perturb_series():
    s = pd.Series(np.arange(10.0), index=pd.bdate_range("2021-01-01", periods=10), name="s")
    p = perturb_future(s, s.index[4], mode="shock")
    assert (p.iloc[:5] == s.iloc[:5]).all()
    assert (p.iloc[5:] != s.iloc[5:]).all()
    assert p.name == "s"


# ------------------------------------------------------------------ correct code
def causal_zscore_last(data: pd.DataFrame, o: ForecastOrigin) -> float:
    h = o.history(data)["x"]
    return float((h.iloc[-1] - h.mean()) / h.std())


def causal_ar1_forecast(data: pd.DataFrame, o: ForecastOrigin) -> float:
    x = o.history(data)["x"].to_numpy()
    beta = np.polyfit(x[:-1], x[1:], 1)
    return float(np.polyval(beta, x[-1]))


def test_correct_functions_pass(random_frame, origin):
    assert_future_invariant(causal_zscore_last, random_frame, origin)
    assert_future_invariant(causal_ar1_forecast, random_frame, origin)


# ------------------------------------------------------------ negative controls
def leaky_full_sample_scaler(data: pd.DataFrame, o: ForecastOrigin) -> float:
    x = data["x"]
    z = (x - x.mean()) / x.std()  # scaler fitted on ALL data, then sliced -> leak
    return float(o.history(z.to_frame())["x"].iloc[-1])


def leaky_centred_window(data: pd.DataFrame, o: ForecastOrigin) -> float:
    smooth = data["x"].rolling(11, center=True, min_periods=1).mean()  # uses t+1..t+5
    return float(smooth.loc[: o.timestamp].iloc[-1])


def leaky_direct_regression(data: pd.DataFrame, o: ForecastOrigin) -> float:
    """h=5 direct regression that forgets to drop rows whose label is not yet realised."""
    h = 5
    x = data["x"]
    y = x.shift(-h)  # label = value h days ahead
    train = pd.concat([x, y], axis=1, keys=["x", "y"]).loc[: o.timestamp].dropna()
    beta = np.polyfit(train["x"], train["y"], 1)
    return float(np.polyval(beta, x.loc[: o.timestamp].iloc[-1]))


def leaky_hyperparameter_choice(data: pd.DataFrame, o: ForecastOrigin) -> float:
    """Chooses a smoothing window using the FULL sample, then forecasts causally."""
    x = data["x"]
    best, best_err = 1, np.inf
    for w in (1, 2, 5, 10, 20):
        err = float(((x - x.rolling(w).mean().shift(1)) ** 2).mean())
        if err < best_err:
            best, best_err = w, err
    return float(o.history(data)["x"].rolling(best).mean().iloc[-1]) + 0.0 * best


def test_negative_controls_are_detected(random_frame, origin):
    assert not is_future_invariant(leaky_full_sample_scaler, random_frame, origin)
    assert not is_future_invariant(leaky_centred_window, random_frame, origin)
    assert not is_future_invariant(leaky_direct_regression, random_frame, origin)


def test_hyperparameter_leak_detected_or_output_encodes_choice(random_frame):
    # Hyper-parameter leaks change the output only if the chosen value changes.
    # Across several origins and a 'shock' perturbation at least one must flip.
    detected = False
    for pos in (150, 200, 250, 300):
        o = ForecastOrigin(random_frame.index[pos])
        if not is_future_invariant(leaky_hyperparameter_choice, random_frame, o):
            detected = True
            break
    assert detected


def test_label_mask_fixes_direct_regression(random_frame, origin):
    def fixed(data: pd.DataFrame, o: ForecastOrigin) -> float:
        h = 5
        hist = o.history(data)["x"]
        y = hist.shift(-h)
        ok = o.label_available_mask(hist.index, h)
        train = pd.DataFrame({"x": hist, "y": y})[ok]
        beta = np.polyfit(train["x"], train["y"], 1)
        return float(np.polyval(beta, hist.iloc[-1]))

    assert_future_invariant(fixed, random_frame, origin)
