"""Seeding, hashing and provenance helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsfm_rc.cli import main
from tsfm_rc.hashing import sha256_array, sha256_file, sha256_frame, sha256_json
from tsfm_rc.provenance import (
    package_versions,
    provenance_record,
    read_parquet_provenance,
    write_parquet_with_provenance,
)
from tsfm_rc.seeding import derive_seed, rng, seed_everything


def test_derive_seed_deterministic_and_key_sensitive():
    assert derive_seed(1, "a", 2) == derive_seed(1, "a", 2)
    assert derive_seed(1, "a", 2) != derive_seed(1, "a", 3)
    assert derive_seed(1, "a") != derive_seed(2, "a")
    assert 0 <= derive_seed(123, "x") < 2**32
    np.testing.assert_array_equal(rng(5, "k").normal(size=3), rng(5, "k").normal(size=3))


def test_seed_everything_reproducible():
    seed_everything(42)
    a = np.random.rand(3)
    seed_everything(42)
    b = np.random.rand(3)
    np.testing.assert_array_equal(a, b)


def test_sha256_known_value(tmp_path):
    p = tmp_path / "f.txt"
    p.write_bytes(b"abc")
    # NIST FIPS 180-2 test vector for "abc"
    assert sha256_file(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_hash_helpers_sensitive_to_content():
    assert sha256_json({"a": 1, "b": 2}) == sha256_json({"b": 2, "a": 1})
    a = np.arange(5.0)
    assert sha256_array(a) != sha256_array(a.astype(np.float32))
    df = pd.DataFrame({"x": [1.0, 2.0]}, index=pd.to_datetime(["2020-01-01", "2020-01-02"]))
    df2 = df.copy()
    df2.iloc[1, 0] = 2.0000001
    assert sha256_frame(df) == sha256_frame(df.copy())
    assert sha256_frame(df) != sha256_frame(df2)


def test_parquet_provenance_roundtrip(tmp_path):
    df = pd.DataFrame({"a": [1, 2]})
    prov = provenance_record(config_hash="c" * 64, data_hash="d" * 64)
    assert prov["packages"]["numpy"] == np.__version__
    p = tmp_path / "x.parquet"
    write_parquet_with_provenance(df, p, prov)
    back = read_parquet_provenance(p)
    assert back["config_hash"] == "c" * 64
    pd.testing.assert_frame_equal(pd.read_parquet(p), df)


def test_package_versions_marks_missing():
    v = package_versions(("numpy", "definitely-not-a-real-package-xyz"))
    assert v["definitely-not-a-real-package-xyz"] == "not-installed"


def test_cli_validate(capsys):
    assert main(["validate", "configs/smoke.yaml"]) == 0
    assert "config_hash=" in capsys.readouterr().out
