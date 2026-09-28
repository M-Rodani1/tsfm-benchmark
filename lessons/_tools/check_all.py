"""Run every lesson browser-like (solution must pass, starter must fail) in *this* interpreter.

Used by CI with Python 3.14 and exactly the package versions of the Pyodide release the site
uses (site/src/generated/runtime.json), so version differences (e.g. pandas 3 vs 2) surface
here with a clear traceback, before the real-browser test:

    PYTHONPATH=src python lessons/_tools/check_all.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from content import lesson_dirs  # noqa: E402


def main() -> int:
    bad = 0
    for d in lesson_dirs():
        for mode in ("solution", "starter"):
            out = subprocess.run([sys.executable, str(HERE / "run_content.py"), str(d), "--browser-like", "--mode", mode],
                                 capture_output=True, text=True, timeout=900)
            try:
                r = json.loads(out.stdout.strip().splitlines()[-1])
            except (IndexError, json.JSONDecodeError):
                print(f"✗ {d.name} {mode}: crashed\n{out.stderr[-3000:]}")
                bad += 1
                continue
            cells = [c for c in r["cells"] if not c["ok"]]
            ok = not cells and (r["checkpoint"]["passed"] if mode == "solution" else not r["checkpoint"]["passed"])
            print(f"{'✓' if ok else '✗'} {d.name} {mode}")
            for c in cells:
                print(f"    cell {c['step']}:\n{c['error']}")
            if not ok:
                bad += 1
                print(f"    checkpoint: {r['checkpoint']}")
    print(f"{bad} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
