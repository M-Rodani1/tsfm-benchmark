"""Immutable raw-data cache with a manifest.

Layout::

    data/raw/
      manifest.json                      # list of entries (append-only)
      <provider>/<TICKER>__<start>__<end>__<sha12>.csv

Rules
-----
1. A file is written once and never modified. Its name contains the first 12 hex digits
   of its SHA-256, so different content always means a different file.
2. Every write appends a manifest entry: source, provider version, download time (UTC),
   requested and actual date range, row count, full SHA-256, file path.
3. Every read re-hashes the file and raises :class:`CacheIntegrityError` on mismatch.
4. When several entries match a request, the **earliest** download is used, so a study
   keeps using the data it started with even if the source is later revised. Use
   ``prefer="latest"`` deliberately (and record it) to switch.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from tsfm_rc.data.provider import STANDARD_COLUMNS, DataProvider
from tsfm_rc.hashing import sha256_bytes, sha256_file

log = logging.getLogger(__name__)


class CacheIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManifestEntry:
    provider: str
    provider_version: str
    ticker: str
    requested_start: str
    requested_end: str
    first_date: str
    last_date: str
    n_rows: int
    sha256: str
    file: str  # relative to the cache root
    downloaded_utc: str


def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    out = df[STANDARD_COLUMNS].copy()
    out.index = out.index.strftime("%Y-%m-%d")
    out.index.name = "date"
    # default float formatting = shortest round-trip repr: reading the file back gives
    # exactly the floats the provider returned
    out.to_csv(buf, lineterminator="\n")
    return buf.getvalue().encode("utf-8")


class RawCache:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.manifest_path = self.root / "manifest.json"

    # ------------------------------------------------------------ manifest
    def entries(self) -> list[ManifestEntry]:
        if not self.manifest_path.exists():
            return []
        with open(self.manifest_path, encoding="utf-8") as fh:
            return [ManifestEntry(**e) for e in json.load(fh)]

    def _append(self, entry: ManifestEntry) -> None:
        entries = self.entries() + [entry]
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.NamedTemporaryFile("w", delete=False, dir=self.root, suffix=".tmp", encoding="utf-8")
        with tmp as fh:
            json.dump([asdict(e) for e in entries], fh, indent=2)
        os.replace(tmp.name, self.manifest_path)

    def find(self, provider: str, ticker: str, start: dt.date, end: dt.date, prefer: str = "earliest") -> ManifestEntry | None:
        matches = [
            e
            for e in self.entries()
            if e.provider == provider
            and e.ticker == ticker
            and e.requested_start == str(start)
            and e.requested_end == str(end)
        ]
        if not matches:
            return None
        matches.sort(key=lambda e: e.downloaded_utc)
        return matches[0] if prefer == "earliest" else matches[-1]

    # ------------------------------------------------------------ write/read
    def store(self, provider: DataProvider, ticker: str, start: dt.date, end: dt.date, df: pd.DataFrame) -> ManifestEntry:
        data = _to_csv_bytes(df)
        digest = sha256_bytes(data)
        rel = Path(provider.name) / f"{ticker}__{start}__{end}__{digest[:12]}.csv"
        path = self.root / rel
        if path.exists():
            if sha256_file(path) != digest:  # pragma: no cover - would need a hash collision
                raise CacheIntegrityError(f"{path} exists with different content")
            log.info("%s: identical raw file already cached (%s)", ticker, rel)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "xb") as fh:  # 'x' = fail if it exists: never overwrite
                fh.write(data)
            os.chmod(path, 0o444)  # read-only as a guard against accidental edits
        entry = ManifestEntry(
            provider=provider.name,
            provider_version=provider.version(),
            ticker=ticker,
            requested_start=str(start),
            requested_end=str(end),
            first_date=str(df.index.min().date()),
            last_date=str(df.index.max().date()),
            n_rows=int(len(df)),
            sha256=digest,
            file=str(rel),
            downloaded_utc=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        )
        self._append(entry)
        return entry

    def load(self, entry: ManifestEntry) -> pd.DataFrame:
        path = self.root / entry.file
        if not path.exists():
            raise CacheIntegrityError(f"cached file missing: {path}")
        got = sha256_file(path)
        if got != entry.sha256:
            raise CacheIntegrityError(f"hash mismatch for {path}: manifest {entry.sha256[:12]}, file {got[:12]}")
        df = pd.read_csv(path, parse_dates=["date"], index_col="date")
        return df[STANDARD_COLUMNS].astype(float)

    def get_or_fetch(
        self,
        provider: DataProvider,
        ticker: str,
        start: dt.date,
        end: dt.date,
        *,
        allow_fetch: bool,
        prefer: str = "earliest",
    ) -> tuple[pd.DataFrame, ManifestEntry]:
        entry = self.find(provider.name, ticker, start, end, prefer=prefer)
        if entry is None:
            if not allow_fetch:
                raise FileNotFoundError(
                    f"{ticker}: no cached raw data for {provider.name} {start}..{end}. "
                    "Run `make fetch-data` (needs network) first."
                )
            log.info("%s: downloading from %s", ticker, provider.name)
            df = provider.fetch(ticker, start, end)
            entry = self.store(provider, ticker, start, end, df)
        return self.load(entry), entry
