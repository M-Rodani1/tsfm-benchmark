"""Load a cleaned panel for a config: provider -> raw cache -> cleaning -> daily series.

The :class:`Panel` carries two hashes that go into every result's provenance:

- ``raw_hash``   SHA-256 over the (ticker, raw file SHA-256) pairs actually used;
- ``panel_hash`` SHA-256 of the cleaned daily panel (what the models see).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import pandas as pd

from tsfm_rc.config import RunConfig
from tsfm_rc.data.cache import RawCache
from tsfm_rc.data.cleaning import CleaningReport, clean_ohlcv, flag_missing_days
from tsfm_rc.data.provider import FixtureProvider, ProviderError, make_provider
from tsfm_rc.data.targets import daily_series
from tsfm_rc.hashing import sha256_file, sha256_frame, sha256_json
from tsfm_rc.paths import resolve

log = logging.getLogger(__name__)


@dataclass
class Panel:
    daily: dict[str, pd.DataFrame]
    ohlcv: dict[str, pd.DataFrame]
    calendar: pd.DatetimeIndex
    cleaning: CleaningReport
    raw_hash: str
    panel_hash: str
    source: str
    raw_files: dict[str, str] = field(default_factory=dict)  # ticker -> sha256
    unavailable: dict[str, str] = field(default_factory=dict)  # ticker -> reason

    @property
    def tickers(self) -> list[str]:
        return list(self.daily)


def _verify_fixture_manifest(path) -> str:
    """Check the committed fixture against its manifest; return its SHA-256."""
    p = resolve(path)
    digest = sha256_file(p)
    man = p.parent / "MANIFEST.json"
    if man.exists():
        with open(man, encoding="utf-8") as fh:
            expected = json.load(fh)["files"].get(p.name)
        if expected and expected != digest:
            raise RuntimeError(
                f"fixture {p} does not match MANIFEST.json ({digest[:12]} vs {expected[:12]}); "
                "regenerate with `make fixtures` or restore the committed file"
            )
    return digest


def load_panel(cfg: RunConfig, *, allow_fetch: bool = False) -> Panel:
    dc = cfg.data
    provider = make_provider(dc.provider, fixture_file=resolve(dc.fixture_file) if dc.fixture_file else None,
                             csv_dir=resolve(dc.csv_dir) if dc.csv_dir else None)
    raw_frames: dict[str, pd.DataFrame] = {}
    raw_files: dict[str, str] = {}
    unavailable: dict[str, str] = {}

    if isinstance(provider, FixtureProvider):
        digest = _verify_fixture_manifest(dc.fixture_file)
        for t in dc.tickers:
            raw_frames[t] = provider.fetch(t, dc.start, dc.end)
            raw_files[t] = digest
    else:
        cache = RawCache(resolve(dc.raw_dir))
        for t in dc.tickers:
            try:
                df, entry = cache.get_or_fetch(provider, t, dc.start, dc.end, allow_fetch=allow_fetch)
            except (ProviderError, FileNotFoundError) as e:
                log.error("%s UNAVAILABLE: %s", t, e)
                unavailable[t] = str(e)
                continue
            raw_frames[t] = df
            raw_files[t] = entry.sha256

    report = CleaningReport()
    clean: dict[str, pd.DataFrame] = {}
    for t, raw in raw_frames.items():
        c, rep = clean_ohlcv(raw, t, split_threshold=dc.split_suspect_threshold)
        clean[t] = c
        report.extend(rep)
    calendar, miss = flag_missing_days(clean)
    report.extend(miss)

    daily = {t: daily_series(c) for t, c in clean.items()}
    for t, d in daily.items():  # GK is undefined when high == low
        for dd in d.index[d["gk"].isna()]:
            report.add(t, dd, "zero_range", "gk_set_missing")

    raw_hash = sha256_json(sorted(raw_files.items()))
    panel_hash = sha256_json({t: sha256_frame(daily[t]) for t in sorted(daily)})
    log.info("panel: %d tickers, %d calendar days, raw_hash=%s", len(daily), len(calendar), raw_hash[:12])
    return Panel(
        daily=daily,
        ohlcv=clean,
        calendar=calendar,
        cleaning=report,
        raw_hash=raw_hash,
        panel_hash=panel_hash,
        source=provider.name,
        raw_files=raw_files,
        unavailable=unavailable,
    )


def fetch_all(cfg: RunConfig) -> dict[str, str]:
    """Download every ticker of ``cfg`` into the raw cache. Returns ticker -> status."""
    dc = cfg.data
    if dc.provider == "fixture":
        return {t: "fixture (nothing to download)" for t in dc.tickers}
    provider = make_provider(dc.provider, csv_dir=resolve(dc.csv_dir) if dc.csv_dir else None)
    cache = RawCache(resolve(dc.raw_dir))
    status: dict[str, str] = {}
    for t in dc.tickers:
        try:
            _, entry = cache.get_or_fetch(provider, t, dc.start, dc.end, allow_fetch=True)
            status[t] = f"ok {entry.first_date}..{entry.last_date} ({entry.n_rows} rows, sha256 {entry.sha256[:12]})"
        except ProviderError as e:
            status[t] = f"FAILED: {e}"
    return status
