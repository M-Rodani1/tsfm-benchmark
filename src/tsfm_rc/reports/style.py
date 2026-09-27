"""Shared chart style (validated with the dataviz palette validator, light mode).

Colour encodes *role*, never model identity (identity is on the axis labels):
baseline = slot 1 blue, TSFM = slot 2 orange, oracle/reference = slot 3 aqua
(slots 1-3 pass all-pairs CVD and normal-vision checks; aqua is < 3:1 on the surface,
so every mark is labelled and every figure has a table next to it in RESULTS.md).
Sequential magnitude (MCS p-values) uses the single-hue blue ramp.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
ROLE = {"baseline": "#2a78d6", "tsfm": "#eb6834", "oracle": "#1baf7a"}
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

TSFM_NAMES = {"chronos_bolt_tiny", "timesfm_2p5_200m", "moirai_1p1_small",
              "chronos_bolt_base", "chronos_2", "moirai_1p1_base", "moirai_2p0_small"}


def role_of(model: str) -> str:
    if model in TSFM_NAMES:
        return "tsfm"
    if model == "oracle":
        return "oracle"
    return "baseline"


def apply() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": INK_2,
        "axes.titlecolor": INK,
        "axes.titlesize": 11,
        "axes.labelsize": 9,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": MUTED,
        "ytick.color": INK_2,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "legend.frameon": False,
        "font.family": "sans-serif",
        "lines.linewidth": 2.0,
        "svg.hashsalt": "tsfm-rc",  # deterministic SVG ids
        "svg.fonttype": "none",
    })


def save(fig, path_no_ext) -> list[str]:
    """Save PNG and SVG with no timestamps (so reruns produce identical files)."""
    from pathlib import Path

    p = Path(path_no_ext)
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p.with_suffix(".png"), dpi=150, bbox_inches="tight", metadata={"Software": None})
    fig.savefig(p.with_suffix(".svg"), bbox_inches="tight", metadata={"Date": None})
    plt.close(fig)
    return [str(p.with_suffix(".png")), str(p.with_suffix(".svg"))]
