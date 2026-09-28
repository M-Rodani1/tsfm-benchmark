"""Execute one lesson from ``site/content`` the way the website runs it, but in CPython.

    python lessons/_tools/run_content.py <lesson-folder> [--browser-like] [--mode solution|starter]

Runs every ``python`` block in order in one namespace, then the checkpoint (the starter or
the solution) and the lesson's checker, from inside the lesson folder. Prints one JSON
object on the last line: ``{"cells": [...], "checkpoint": {"passed": bool, "error": ...}}``.

``--browser-like`` reproduces the website's environment as closely as CPython can:
- ``TSFM_RC_ROOT`` points at a temporary folder holding *only* the files the site mounts
  (the lesson's ``mounts``: fixtures, configs, published results), so a lesson that silently
  needs ``results/`` Parquet files or anything else fails here;
- packages the browser does not load are blocked: ``arch``, ``lightgbm``, ``pyarrow``,
  ``yfinance``, ``torch``, Hugging Face and the TSFM libraries.
The real browser run is the Playwright test ``site/e2e/exercises.spec.ts`` (CI).
"""

from __future__ import annotations

import argparse
import importlib.abc
import io
import json
import os
import shutil
import sys
import tempfile
import traceback
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from content import load_lesson  # noqa: E402

BLOCKED = ("arch", "lightgbm", "pyarrow", "fastparquet", "yfinance", "torch", "huggingface_hub",
           "chronos", "timesfm", "uni2ts", "gluonts", "transformers")


class _Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ModuleNotFoundError(f"No module named '{name}' (not available in the browser)")
        return None


def mount_files(mounts: list[str]) -> dict[str, Path]:
    """Relative path under TSFM_RC_ROOT -> source file in the repository (same map as the site)."""
    out: dict[str, Path] = {}
    for m in mounts:
        if m == "fixtures":
            for f in ("synthetic_ohlcv.csv", "synthetic_latent.csv", "MANIFEST.json"):
                out[f"data/fixtures/{f}"] = REPO / "data" / "fixtures" / f
        elif m == "configs":
            for f in sorted((REPO / "configs").glob("*.yaml")):
                out[f"configs/{f.name}"] = f
        elif m.startswith("results:"):
            run = m.split(":", 1)[1]
            pub = REPO / "site" / "public" / "data" / "results"
            index = json.loads((pub / "index.json").read_text(encoding="utf-8"))
            entry = next(r for r in index["runs"] if r["run"] == run)
            out["site/public/data/results/index.json"] = pub / "index.json"
            for rel in [*entry["tables"].values(), entry["report"]]:
                out[f"site/public/data/results/{rel}"] = pub / rel
        else:
            raise ValueError(f"unknown mount {m!r}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lesson")
    ap.add_argument("--browser-like", action="store_true")
    ap.add_argument("--mode", choices=["solution", "starter"], default="solution")
    args = ap.parse_args()
    lesson = load_lesson(Path(args.lesson).resolve())
    work = Path(tempfile.mkdtemp(prefix="lesson-"))
    cwd = work / "lesson"
    cwd.mkdir()
    if args.browser_like:
        root = work / "root"
        for rel, src in mount_files(lesson.meta.get("mounts") or []).items():
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        root.mkdir(exist_ok=True)
        os.environ["TSFM_RC_ROOT"] = str(root)
        sys.meta_path.insert(0, _Blocker())
    for a in lesson.meta.get("assets") or []:
        shutil.copyfile(lesson.dir / a, cwd / a)
    (cwd / "checker.py").write_text(lesson.exercise.checker, encoding="utf-8")
    os.chdir(cwd)
    sys.path.insert(0, str(cwd))
    os.environ["MPLBACKEND"] = "Agg"

    ns: dict = {"__name__": "__main__"}
    cells = []
    for step in lesson.steps:
        for b in step.blocks:
            if b.kind != "python":
                continue
            buf = io.StringIO()
            try:
                with redirect_stdout(buf):
                    exec(compile(b.text, f"<{step.id}>", "exec"), ns)
                cells.append({"step": step.id, "ok": True})
            except Exception:
                cells.append({"step": step.id, "ok": False, "error": traceback.format_exc(limit=3)})
            try:
                import matplotlib.pyplot as plt

                plt.close("all")
            except ModuleNotFoundError:
                pass
    code = lesson.exercise.solution if args.mode == "solution" else lesson.exercise.starter
    cp: dict = {}
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            exec(compile(code, "<checkpoint>", "exec"), ns)
            import checker

            checker.check(ns[lesson.exercise.function])
        cp = {"passed": "✅" in buf.getvalue(), "output": buf.getvalue()[-300:]}
    except Exception as e:
        cp = {"passed": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}
    shutil.rmtree(work, ignore_errors=True)
    print(json.dumps({"lesson": lesson.slug, "cells": cells, "checkpoint": cp}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
