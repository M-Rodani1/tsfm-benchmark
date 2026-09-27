"""Providers (with a mocked yfinance) and the immutable raw cache."""

from __future__ import annotations

import datetime as dt
import os
import sys
import types

import numpy as np
import pandas as pd
import pytest

from tsfm_rc.data.cache import CacheIntegrityError, RawCache
from tsfm_rc.data.provider import (
    STANDARD_COLUMNS,
    CSVDirectoryProvider,
    DataProvider,
    ProviderError,
    YFinanceProvider,
    standardise,
)


def yahoo_like(n=5, tz="America/New_York"):
    idx = pd.date_range("2024-01-02 00:00", periods=n, freq="B", tz=tz)
    return pd.DataFrame(
        {"Open": np.arange(n) + 10.0, "High": np.arange(n) + 11.0, "Low": np.arange(n) + 9.0,
         "Close": np.arange(n) + 10.5, "Adj Close": np.arange(n) + 10.4, "Volume": [100] * n,
         "Dividends": 0.0, "Stock Splits": 0.0},
        index=idx,
    )


def test_standardise_yahoo_frame():
    out = standardise(yahoo_like(), "SPY")
    assert list(out.columns) == STANDARD_COLUMNS
    assert out.index.tz is None and out.index.name == "date"
    assert out.index[0] == pd.Timestamp("2024-01-02")
    assert out["adj_close"].iloc[0] == 10.4


def test_standardise_multiindex_and_errors():
    df = yahoo_like()
    df.columns = pd.MultiIndex.from_product([df.columns, ["SPY"]])
    assert list(standardise(df, "SPY").columns) == STANDARD_COLUMNS
    with pytest.raises(ProviderError):
        standardise(pd.DataFrame(), "X")
    with pytest.raises(ProviderError):
        standardise(yahoo_like().drop(columns="Volume"), "X")


class _FakeTicker:
    calls: list = []

    def __init__(self, ticker):
        self.ticker = ticker

    def history(self, **kw):
        _FakeTicker.calls.append(kw)
        if self.ticker == "BAD":
            raise RuntimeError("403 Forbidden")
        return yahoo_like(10)


def test_yfinance_provider_call_contract(monkeypatch):
    fake = types.SimpleNamespace(Ticker=_FakeTicker, __version__="test")
    monkeypatch.setitem(sys.modules, "yfinance", fake)
    p = YFinanceProvider()
    out = p.fetch("SPY", dt.date(2024, 1, 2), dt.date(2024, 1, 10))
    kw = _FakeTicker.calls[-1]
    assert kw["auto_adjust"] is False and kw["repair"] is False and kw["actions"] is True
    assert kw["end"] == "2024-01-11"  # end is exclusive in yfinance, so +1 day
    assert out.index.max() <= pd.Timestamp("2024-01-10")
    with pytest.raises(ProviderError, match="403"):
        p.fetch("BAD", dt.date(2024, 1, 2), dt.date(2024, 1, 10))
    assert p.version() == "test"


def test_csv_directory_provider(tmp_path):
    df = yahoo_like(6, tz=None).reset_index(names="Date")
    df.to_csv(tmp_path / "ABC.csv", index=False)
    out = CSVDirectoryProvider(tmp_path).fetch("ABC", dt.date(2024, 1, 1), dt.date(2024, 1, 5))
    assert len(out) == 4
    with pytest.raises(ProviderError):
        CSVDirectoryProvider(tmp_path).fetch("NOPE", dt.date(2024, 1, 1), dt.date(2024, 1, 5))


class _StubProvider(DataProvider):
    name = "stub"

    def __init__(self):
        self.n_calls = 0

    def fetch(self, ticker, start, end):
        self.n_calls += 1
        return standardise(yahoo_like(8), ticker)


def test_cache_store_load_roundtrip_and_manifest(tmp_path):
    cache = RawCache(tmp_path)
    prov = _StubProvider()
    s, e = dt.date(2024, 1, 1), dt.date(2024, 1, 31)
    df, entry = cache.get_or_fetch(prov, "SPY", s, e, allow_fetch=True)
    assert prov.n_calls == 1
    df2, entry2 = cache.get_or_fetch(prov, "SPY", s, e, allow_fetch=True)
    assert prov.n_calls == 1  # served from cache
    pd.testing.assert_frame_equal(df, df2)
    pd.testing.assert_frame_equal(df, prov.fetch("SPY", s, e), check_freq=False)  # exact floats
    assert entry == entry2 and entry.n_rows == 8 and len(entry.sha256) == 64
    assert (tmp_path / entry.file).exists()
    assert not os.access(tmp_path / entry.file, os.W_OK) or os.geteuid() == 0


def test_cache_never_overwrites_and_detects_tampering(tmp_path):
    cache = RawCache(tmp_path)
    prov = _StubProvider()
    s, e = dt.date(2024, 1, 1), dt.date(2024, 1, 31)
    _, entry = cache.get_or_fetch(prov, "SPY", s, e, allow_fetch=True)
    path = tmp_path / entry.file
    os.chmod(path, 0o644)
    path.write_text(path.read_text().replace("10.4", "99.9"))
    with pytest.raises(CacheIntegrityError, match="hash mismatch"):
        cache.load(entry)


def test_cache_without_fetch_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="make fetch-data"):
        RawCache(tmp_path).get_or_fetch(_StubProvider(), "SPY", dt.date(2024, 1, 1), dt.date(2024, 2, 1), allow_fetch=False)


def test_cache_prefers_earliest_download(tmp_path):
    cache = RawCache(tmp_path)
    prov = _StubProvider()
    s, e = dt.date(2024, 1, 1), dt.date(2024, 1, 31)
    first = cache.store(prov, "SPY", s, e, standardise(yahoo_like(8), "SPY"))
    revised = standardise(yahoo_like(8), "SPY")
    revised.iloc[0, 0] = 10.01  # the source revised a value
    import time

    time.sleep(1.1)
    second = cache.store(prov, "SPY", s, e, revised)
    assert first.file != second.file
    assert cache.find("stub", "SPY", s, e).sha256 == first.sha256
    assert cache.find("stub", "SPY", s, e, prefer="latest").sha256 == second.sha256
