"""``make doctor``: check the environment, data cache and model availability.

Each check prints OK / WARN / FAIL and, when something is wrong, one plain-English sentence
saying what to do. Nothing here downloads anything unless ``--online`` is given.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import shutil
import sys
from dataclasses import dataclass
from importlib import metadata

from tsfm_rc.paths import FIXTURE_DIR, LESSONS_DIR, RAW_DIR, RESULTS_DIR, ROOT


@dataclass
class Check:
    name: str
    status: str  # OK / WARN / FAIL
    detail: str
    fix: str = ""


def _pkg(dist: str) -> str | None:
    try:
        return metadata.version(dist)
    except metadata.PackageNotFoundError:
        return None


def check_python() -> Check:
    v = sys.version_info
    if (v.major, v.minor) == (3, 11):
        return Check("Python", "OK", f"{sys.version.split()[0]} ({sys.executable})")
    return Check("Python", "FAIL", f"{sys.version.split()[0]}",
                 "This project needs Python 3.11. Run `uv python install 3.11` and then `uv sync`.")


def check_uv() -> Check:
    if shutil.which("uv"):
        return Check("uv", "OK", "found on PATH")
    return Check("uv", "WARN", "not on PATH",
                 "Install uv (https://docs.astral.sh/uv/) so `make` commands use the locked environment.")


def check_core_packages() -> list[Check]:
    out = []
    for dist in ("numpy", "pandas", "scipy", "statsmodels", "arch", "lightgbm", "pydantic", "pyarrow", "matplotlib", "yfinance"):
        v = _pkg(dist)
        out.append(Check(f"package {dist}", "OK" if v else "FAIL", v or "missing",
                         "" if v else "Run `make install` (or `uv sync`) to install the locked environment."))
    return out


def check_lock_sync() -> Check:
    """Compare installed versions with uv.lock for the core packages."""
    lock = ROOT / "uv.lock"
    if not lock.exists():
        return Check("uv.lock", "FAIL", "missing", "Restore uv.lock from git: `git checkout uv.lock`.")
    text = lock.read_text(encoding="utf-8")
    mismatches = []
    for dist in ("numpy", "pandas", "scipy", "arch", "lightgbm", "statsmodels"):
        block = text.split(f'\nname = "{dist}"\nversion = "', 1)
        if len(block) == 2:
            locked = block[1].split('"', 1)[0]
            if _pkg(dist) and _pkg(dist) != locked:
                mismatches.append(f"{dist} {_pkg(dist)} (lock {locked})")
    if mismatches:
        return Check("installed = locked", "WARN", "; ".join(mismatches),
                     "Your environment drifted from uv.lock. Run `make install` to restore exact versions.")
    return Check("installed = locked", "OK", "core numeric packages match uv.lock")


def check_fixtures() -> Check:
    man = FIXTURE_DIR / "MANIFEST.json"
    if not man.exists():
        return Check("fixtures", "FAIL", "data/fixtures/MANIFEST.json missing", "Run `make fixtures` or `git checkout data/fixtures`.")
    from tsfm_rc.hashing import sha256_file

    files = json.loads(man.read_text())["files"]
    bad = [f for f, h in files.items() if not (FIXTURE_DIR / f).exists() or sha256_file(FIXTURE_DIR / f) != h]
    if bad:
        return Check("fixtures", "FAIL", f"hash mismatch: {bad}",
                     "A fixture file was modified. Restore it with `git checkout data/fixtures` (or regenerate: `make fixtures`).")
    return Check("fixtures", "OK", f"{len(files)} files match their SHA-256")


def check_raw_cache() -> Check:
    from tsfm_rc.data.cache import CacheIntegrityError, RawCache

    cache = RawCache(RAW_DIR)
    entries = cache.entries()
    if not entries:
        return Check("real-data cache", "WARN", "empty (no Yahoo downloads yet)",
                     "Only needed for the real study: run `make fetch-data` (needs internet). Fixtures work offline.")
    bad = []
    for e in entries:
        try:
            cache.load(e)
        except (CacheIntegrityError, FileNotFoundError, OSError) as ex:
            bad.append(f"{e.ticker}: {ex}")
    if bad:
        return Check("real-data cache", "FAIL", "; ".join(bad[:3]),
                     "A cached raw file changed or disappeared. Delete its manifest entry and re-run `make fetch-data`.")
    tickers = sorted({e.ticker for e in entries})
    return Check("real-data cache", "OK", f"{len(entries)} verified downloads, {len(tickers)} tickers")


def check_tsfm_packages() -> list[Check]:
    out = []
    for mod, dist in (("torch", "torch"), ("chronos", "chronos-forecasting"), ("timesfm", "timesfm"), ("uni2ts", "uni2ts")):
        if importlib.util.find_spec(mod) is None:
            out.append(Check(f"TSFM package {dist}", "WARN", "not installed",
                             "Needed only for the foundation models: run `make install-tsfm` (downloads PyTorch, ~6 GB)."))
            continue
        try:
            importlib.import_module(mod)
            out.append(Check(f"TSFM package {dist}", "OK", _pkg(dist) or "?"))
        except Exception as e:  # pragma: no cover - broken installs
            out.append(Check(f"TSFM package {dist}", "FAIL", f"import error: {type(e).__name__}: {str(e)[:120]}",
                             "The package is installed but broken. Run `make install-tsfm` again."))
    return out


def check_weights(online: bool) -> list[Check]:
    from tsfm_rc.config import load_config

    out = []
    try:
        from huggingface_hub import scan_cache_dir
    except ImportError:
        return [Check("model weights", "WARN", "huggingface_hub not installed", "Run `make install-tsfm`.")]
    try:
        cached = {r.repo_id for r in scan_cache_dir().repos}
    except Exception:
        cached = set()
    for spec in load_config("configs/default.yaml").models.tsfms:
        if spec.hf_id in cached:
            out.append(Check(f"weights {spec.name}", "OK", f"{spec.hf_id} in the local Hugging Face cache"))
            continue
        if online:
            from tsfm_rc.models.tsfm import TSFMUnavailable, fetch_weights

            try:
                _, rev, _ = fetch_weights(spec.hf_id, spec.revision)
                out.append(Check(f"weights {spec.name}", "OK", f"downloaded {spec.hf_id} @ {rev[:10]}"))
            except TSFMUnavailable as e:
                out.append(Check(f"weights {spec.name}", "FAIL", str(e)[:160],
                                 "Check your internet connection/proxy; the model will be reported UNAVAILABLE until this works."))
        else:
            out.append(Check(f"weights {spec.name}", "WARN", f"{spec.hf_id} not downloaded yet",
                             "They download automatically on the first `make reproduce`; or run `make doctor ONLINE=1` to fetch now."))
    return out


def check_results() -> Check:
    runs = sorted(p.name for p in RESULTS_DIR.iterdir() if (p / "stats").exists()) if RESULTS_DIR.exists() else []
    if not runs:
        return Check("results", "WARN", "no stored results", "Run `make smoke` (about a minute, offline).")
    return Check("results", "OK", f"stored runs: {', '.join(runs)}")


def check_lessons() -> Check:
    lessons = sorted(p.name for p in LESSONS_DIR.iterdir() if p.is_dir() and p.name[:2].isdigit())
    missing = [n for n in lessons if not (LESSONS_DIR / n / "lesson.ipynb").exists()]
    if missing:
        return Check("lessons", "WARN", f"notebooks missing: {missing}", "Run `make lessons` to rebuild them from lesson.py.")
    jl = _pkg("jupyterlab")
    return Check("lessons", "OK" if jl else "WARN", f"{len(lessons)} lessons" + ("" if jl else "; JupyterLab not installed"),
                 "" if jl else "To open the notebooks run `make install-all`, then `uv run jupyter lab`.")


def run_doctor(online: bool = False) -> int:
    checks: list[Check] = [check_python(), check_uv(), *check_core_packages(), check_lock_sync(), check_fixtures(),
                           check_raw_cache(), *check_tsfm_packages(), *check_weights(online), check_results(), check_lessons()]
    width = max(len(c.name) for c in checks)
    icon = {"OK": "✓", "WARN": "!", "FAIL": "✗"}
    for c in checks:
        print(f" {icon[c.status]} {c.status:4s}  {c.name:<{width}}  {c.detail}")
        if c.fix:
            print(f" {'':6s}  {'':<{width}}  → {c.fix}")
    n_fail = sum(c.status == "FAIL" for c in checks)
    n_warn = sum(c.status == "WARN" for c in checks)
    print()
    if n_fail:
        print(f"{n_fail} problem(s) to fix (✗). Follow the → lines above, then run `make doctor` again.")
    elif n_warn:
        print(f"Everything needed for tests, lessons and `make smoke` works. {n_warn} optional item(s) (!) matter only for the real study.")
    else:
        print("All checks passed.")
    return 1 if n_fail else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(run_doctor(online=os.environ.get("ONLINE") == "1"))
