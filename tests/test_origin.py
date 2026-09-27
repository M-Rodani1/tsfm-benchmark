"""Tests for the ForecastOrigin abstraction (the single slicing point)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tsfm_rc.origin import ForecastOrigin, LeakageError, make_origin_schedule


def test_history_excludes_future_and_includes_origin(random_frame):
    t = random_frame.index[100]
    o = ForecastOrigin(t)
    h = o.history(random_frame)
    assert h.index.max() == t
    assert len(h) == 101
    assert (h.index <= t).all()


def test_history_is_a_copy(random_frame):
    o = ForecastOrigin(random_frame.index[50])
    h = o.history(random_frame)
    h.iloc[0, 0] = 1e9
    assert random_frame.iloc[0, 0] != 1e9


def test_history_origin_not_in_index_uses_last_available(random_frame):
    # A Saturday is not a business day: history ends on the Friday before.
    sat = pd.Timestamp("2020-01-04")
    o = ForecastOrigin(sat)
    h = o.history(random_frame)
    assert h.index.max() == pd.Timestamp("2020-01-03")


def test_history_rejects_unsorted_and_non_datetime():
    df = pd.DataFrame({"a": [1, 2, 3]}, index=pd.to_datetime(["2020-01-03", "2020-01-01", "2020-01-02"]))
    with pytest.raises(ValueError):
        ForecastOrigin("2020-01-02").history(df)
    with pytest.raises(TypeError):
        ForecastOrigin("2020-01-02").history(pd.DataFrame({"a": [1, 2]}))


def test_assert_no_future(random_frame):
    o = ForecastOrigin(random_frame.index[10])
    o.assert_no_future(random_frame.iloc[:11])
    with pytest.raises(LeakageError):
        o.assert_no_future(random_frame.iloc[:12])


@pytest.mark.parametrize("h", [1, 5, 20])
def test_label_available_mask(bday_index, h):
    t_pos = 200
    o = ForecastOrigin(bday_index[t_pos])
    mask = o.label_available_mask(bday_index, h)
    # Row i is usable iff its label window (i, i+h] ends at or before the origin.
    expected = np.arange(len(bday_index)) + h <= t_pos
    np.testing.assert_array_equal(mask, expected)
    assert mask.sum() == t_pos - h + 1
    # The last usable row's label ends exactly at the origin.
    last = np.flatnonzero(mask)[-1]
    assert last + h == t_pos


def test_label_mask_invalid_horizon(bday_index):
    with pytest.raises(ValueError):
        ForecastOrigin(bday_index[5]).label_available_mask(bday_index, 0)


def test_schedule_respects_test_start_stride_and_min_train(bday_index):
    origins = make_origin_schedule(bday_index, "2020-03-02", stride=5, min_train_obs=100)
    first_pos = bday_index.get_loc(origins[0].timestamp)
    assert first_pos >= 99  # at least 100 observations up to and including origin
    assert origins[0].timestamp >= pd.Timestamp("2020-03-02")
    gaps = np.diff([bday_index.get_loc(o.timestamp) for o in origins])
    assert (gaps == 5).all()
    assert [o.ordinal for o in origins] == list(range(len(origins)))


def test_schedule_end_and_empty(bday_index):
    origins = make_origin_schedule(bday_index, bday_index[0], stride=1, min_train_obs=1, end=bday_index[9])
    assert len(origins) == 10
    assert make_origin_schedule(bday_index, "2030-01-01", stride=1, min_train_obs=1) == []
    with pytest.raises(ValueError):
        make_origin_schedule(bday_index, bday_index[0], stride=0, min_train_obs=1)
