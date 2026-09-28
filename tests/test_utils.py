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


def test_cli_pins_openblas_kernel_before_numpy_loads():
    """D-054: `tsfm-rc` pins OpenBLAS's generic kernels on x86-64 (bit-for-bit reproducible
    GARCH fits across CPUs) before NumPy is imported; an explicit choice is respected."""
    import os
    import platform
    import subprocess
    import sys

    # record OPENBLAS_CORETYPE at the moment NumPy is first imported (when OpenBLAS loads)
    code = (
        "import os, sys\n"
        "class Hook:\n"
        "    def find_spec(self, name, path, target=None):\n"
        "        if name == 'numpy' and not hasattr(sys, '_seen'):\n"
        "            sys._seen = os.environ.get('OPENBLAS_CORETYPE')\n"
        "sys.meta_path.insert(0, Hook())\n"
        "import tsfm_rc.cli\n"
        "print(sys._seen)\n"
    )
    env = {k: v for k, v in os.environ.items() if k != "OPENBLAS_CORETYPE"}
    run = lambda e: subprocess.run([sys.executable, "-c", code], env=e, capture_output=True, text=True, check=True).stdout.strip()  # noqa: E731
    x86 = platform.machine().lower() in ("x86_64", "amd64")
    assert run(env) == ("Prescott" if x86 else "None")
    assert run({**env, "OPENBLAS_CORETYPE": "Haswell"}) == "Haswell"
    # imported as a library after NumPy: left alone (children would otherwise differ from the parent)
    late = "import numpy, os, tsfm_rc.cli; print(os.environ.get('OPENBLAS_CORETYPE'))"
    assert subprocess.run([sys.executable, "-c", late], env=env, capture_output=True, text=True, check=True).stdout.strip() == "None"
    assert provenance_record(config_hash="c", data_hash="d")["openblas_coretype"] == os.environ.get("OPENBLAS_CORETYPE", "auto")


def test_package_versions_marks_missing():
    v = package_versions(("numpy", "definitely-not-a-real-package-xyz"))
    assert v["definitely-not-a-real-package-xyz"] == "not-installed"


def test_cli_validate(capsys):
    assert main(["validate", "configs/smoke.yaml"]) == 0
    assert "config_hash=" in capsys.readouterr().out


def test_pretraining_checklist_covers_every_unverified_tag():
    """Every [S]/[M]/[UNVERIFIED] claim in docs/PRETRAINING-DATA.md is on the checklist at the top."""
    import re

    from tsfm_rc.paths import DOCS_DIR

    text = (DOCS_DIR / "PRETRAINING-DATA.md").read_text(encoding="utf-8")
    head, body = text.split("\n---\n", 1)
    ids = set(re.findall(r"^\| \[[ x]\] \| ([A-Z]\d+) \|", head, flags=re.M))
    assert len(ids) >= 14
    rows = [ln for ln in body.splitlines() if ln.startswith("|") and re.search(r"\[(S|M|UNVERIFIED)\]", ln)
            and not ln.startswith("| **[")]  # the tag legend itself
    assert rows, "expected tagged table rows"
    for ln in rows:
        refs = set(re.findall(r"\(([CTM]\d+)(?:, ([CTM]\d+))?\)", ln.split("|")[1]))
        flat = {r for pair in refs for r in pair if r}
        assert flat and flat <= ids, f"unverified claim without a checklist entry: {ln[:90]}"
