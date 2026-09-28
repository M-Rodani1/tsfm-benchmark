"""Number formatting shared by the report, the lessons and the website export.

Kept free of plotting imports so it loads quickly in the browser (Pyodide).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def fp(p) -> str:
    if p is None or not np.isfinite(p):
        return "–"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def f3(x) -> str:
    return "–" if x is None or not np.isfinite(x) else f"{x:.3f}"


def f2(x) -> str:
    return "–" if x is None or not np.isfinite(x) else f"{x:.2f}"


def ci(r, lo, hi) -> str:
    if not np.isfinite(r):
        return "–"
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return f"{r:.3f}"
    return f"{r:.3f} [{lo:.3f}, {hi:.3f}]"


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "*(no rows)*\n"
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(lines) + "\n"
