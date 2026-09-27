"""Figures for RESULTS.md, drawn only from stored stats tables (no new statistics)."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from matplotlib.ticker import FormatStrFormatter

from tsfm_rc.reports import style

TARGET_TITLE = {"returns": "Returns (MSE)", "rv": "Realised volatility (QLIKE)", "volume": "Log volume (MSE)"}


def _role_legend(ax, roles) -> None:
    handles = [Line2D([], [], marker="o", ls="", color=style.ROLE[r], label=r.upper() if r == "tsfm" else r) for r in roles]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.0, 1.0))



def forest_relative_loss(dm_all: pd.DataFrame, out_dir: Path, period: str = "full", window: str = "expanding") -> list[str]:
    """Relative loss (model / reference) with 95% bootstrap CI, per target, rows = model x horizon."""
    D = dm_all[(dm_all["period"] == period) & (dm_all["window"] == window)]
    if D.empty:
        return []
    targets = [t for t in ("returns", "rv", "volume") if t in set(D["target"])]
    heights = [max(2.0, 0.22 * len(D[D["target"] == t]) + 0.8) for t in targets]
    fig, axes = plt.subplots(len(targets), 1, figsize=(7.5, sum(heights)), gridspec_kw={"height_ratios": heights})
    axes = np.atleast_1d(axes)
    for ax, t in zip(axes, targets, strict=True):
        S = D[D["target"] == t].sort_values(["horizon", "model"])
        y = np.arange(len(S))[::-1]
        for yi, r in zip(y, S.itertuples(index=False), strict=True):
            c = style.ROLE[style.role_of(r.model)]
            if np.isfinite(r.rel_loss_lo):
                ax.plot([r.rel_loss_lo, r.rel_loss_hi], [yi, yi], color=c, lw=2, solid_capstyle="round")
            ax.plot([r.rel_loss], [yi], "o", color=c, ms=6, mec=style.SURFACE, mew=1.5)
        ax.axvline(1.0, color=style.MUTED, lw=1, ls="--")
        ax.set_yticks(y, [f"{m}  h={h}" for m, h in zip(S["model"], S["horizon"], strict=True)])
        ax.xaxis.set_major_formatter(FormatStrFormatter("%.2f"))
        ref = S["reference"].iloc[0]
        ax.set_title(f"{TARGET_TITLE[t]}: loss relative to {ref} (left of dashed line = better)", loc="left")
        ax.grid(axis="y", visible=False)
        _role_legend(ax, sorted({style.role_of(m) for m in S["model"]}))
    fig.tight_layout()
    return style.save(fig, out_dir / f"relative_loss_{period}_{window}")


def cumulative_loss_diff(series: pd.DataFrame, out_dir: Path, horizon: int = 1) -> list[str]:
    """Small multiples: cumulative pooled loss differential over time (model - reference)."""
    S = series[(series["horizon"] == horizon) & (series.get("ticker", "POOLED") == "POOLED")
               & (series.get("window", "expanding") == "expanding")]
    if S.empty:
        return []
    paths = []
    for t, G in S.groupby("target"):
        models = sorted(G["model"].unique())
        n = len(models)
        cols = min(3, n)
        rows = int(np.ceil(n / cols))
        fig, axes = plt.subplots(rows, cols, figsize=(3.2 * cols, 2.2 * rows), sharey=True, squeeze=False)
        for ax, m in zip(axes.flat, models, strict=False):
            g = G[G["model"] == m].sort_values("origin")
            ax.plot(pd.to_datetime(g["origin"]), g["cum_diff"], color=style.ROLE[style.role_of(m)])
            ax.axhline(0, color=style.AXIS, lw=1)
            ax.set_title(m, loc="left", fontsize=9)
            ax.tick_params(axis="x", labelrotation=30)
        for ax in list(axes.flat)[n:]:
            ax.set_visible(False)
        ref = G["reference"].iloc[0]
        fig.suptitle(f"{TARGET_TITLE[t]}, h={horizon}: cumulative loss minus {ref} (falling = model better)",
                     x=0.01, ha="left", fontsize=10, color=style.INK)
        fig.tight_layout()
        paths += style.save(fig, out_dir / f"cumulative_diff_{t}_h{horizon}")
    return paths


def mcs_heatmap(mcs: pd.DataFrame, out_dir: Path, period: str) -> list[str]:
    M = mcs[(mcs["period"] == period) & (mcs["ticker"] == "POOLED")]
    if M.empty:
        return []
    M = M.assign(col=M["target"] + " h=" + M["horizon"].astype(str))
    P = M.pivot_table(index="model", columns="col", values="mcs_pvalue")
    IN = M.pivot_table(index="model", columns="col", values="in_mcs", aggfunc="max")
    keys = M.drop_duplicates("col").set_index("col")[["target", "horizon"]]
    tord = {"returns": 0, "rv": 1, "volume": 2}
    order = sorted(P.columns, key=lambda c: (tord.get(keys.loc[c, "target"], 9), int(keys.loc[c, "horizon"])))
    P, IN = P[order], IN.reindex(index=P.index, columns=order)
    fig, ax = plt.subplots(figsize=(1.0 + 0.9 * P.shape[1], 0.9 + 0.35 * P.shape[0]))
    cmap = ListedColormap(style.SEQ_BLUE)
    im = ax.imshow(P.to_numpy(dtype=float), cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(P.shape[1]), P.columns, rotation=40, ha="right")
    ax.set_yticks(range(P.shape[0]), P.index)
    ax.grid(False)
    for i in range(P.shape[0]):
        for j in range(P.shape[1]):
            v = P.iat[i, j]
            if np.isfinite(v):
                inside = "in MCS" if bool(IN.iat[i, j]) else ""
                ax.text(j, i, f"{v:.2f}\n{inside}".strip(), ha="center", va="center", fontsize=7,
                        color="#ffffff" if v > 0.5 else style.INK)
    cb = fig.colorbar(im, ax=ax, fraction=0.04)
    cb.set_label("MCS p-value")
    ax.set_title(f"Model Confidence Set p-values ({period}); blank = model not evaluated", loc="left")
    fig.tight_layout()
    return style.save(fig, out_dir / f"mcs_{period}")


def contamination_forest(con: pd.DataFrame, out_dir: Path) -> list[str]:
    C = con[(con.get("status", "AVAILABLE") == "AVAILABLE") & con["delta"].notna()] if "delta" in con else pd.DataFrame()
    if C.empty:
        return []
    C = C.sort_values(["target", "horizon", "windows_of", "role"])
    fig, ax = plt.subplots(figsize=(7.5, 0.8 + 0.2 * len(C)))
    y = np.arange(len(C))[::-1]
    for yi, r in zip(y, C.itertuples(index=False), strict=True):
        c = style.ROLE["tsfm" if r.role == "tsfm" else "baseline"]
        ax.plot([r.ci_lo, r.ci_hi], [yi, yi], color=c, lw=2)
        ax.plot([r.delta], [yi], "o", color=c, ms=6, mec=style.SURFACE, mew=1.5)
    ax.axvline(0, color=style.MUTED, lw=1, ls="--")
    ax.set_yticks(y, [f"{r.target} h={r.horizon} · {r.model} (windows of {r.windows_of})" for r in C.itertuples()], fontsize=7)
    ax.set_title("Contamination statistic Δ = ln R_clean − ln R_seen (>0 = relatively better where data possibly seen)", loc="left", fontsize=9)
    ax.grid(axis="y", visible=False)
    labels = {"tsfm": "TSFM", "placebo": "placebo (baseline)"}
    handles = [Line2D([], [], marker="o", ls="", color=style.ROLE["tsfm" if r == "tsfm" else "baseline"], label=labels[r])
               for r in ("tsfm", "placebo") if r in set(C["role"])]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    return style.save(fig, out_dir / "contamination")


def synthetic_ratio(syn: pd.DataFrame, out_dir: Path) -> list[str]:
    if syn is None or syn.empty:
        return []
    S = syn[syn["model"] != "oracle"].sort_values(["target", "horizon", "model"])
    fig, ax = plt.subplots(figsize=(7.5, 0.8 + 0.2 * len(S)))
    y = np.arange(len(S))[::-1]
    for yi, r in zip(y, S.itertuples(index=False), strict=True):
        ax.plot([1.0, r.ratio_to_oracle], [yi, yi], color=style.AXIS, lw=1)
        ax.plot([r.ratio_to_oracle], [yi], "o", color=style.ROLE[style.role_of(r.model)], ms=6)
    ax.axvline(1.0, color=style.ROLE["oracle"], lw=1.5, ls="--", label="oracle (= 1)")
    ax.set_yticks(y, [f"{r.target} h={r.horizon} · {r.model}" for r in S.itertuples()], fontsize=7)
    ax.xaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    ax.set_title("Synthetic control: mean primary loss relative to the oracle (1 = optimal)", loc="left", fontsize=9)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    return style.save(fig, out_dir / "synthetic_control")


def make_all(tables: dict[str, pd.DataFrame], out_dir: Path) -> dict[str, list[str]]:
    style.apply()
    out = {}
    if "dm_all" in tables and len(tables["dm_all"]):
        out["relative_loss_full"] = forest_relative_loss(tables["dm_all"], out_dir, "full")
        out["relative_loss_clean"] = forest_relative_loss(tables["dm_all"], out_dir, "common_clean")
    if "loss_diff_series" in tables and len(tables["loss_diff_series"]):
        out["cumulative_h1"] = cumulative_loss_diff(tables["loss_diff_series"], out_dir, 1)
    if "mcs" in tables and len(tables["mcs"]):
        out["mcs_full"] = mcs_heatmap(tables["mcs"], out_dir, "full")
        out["mcs_clean"] = mcs_heatmap(tables["mcs"], out_dir, "common_clean")
    if "contamination" in tables and len(tables["contamination"]):
        out["contamination"] = contamination_forest(tables["contamination"], out_dir)
    if "synthetic" in tables and len(tables["synthetic"]):
        out["synthetic"] = synthetic_ratio(tables["synthetic"], out_dir)
    return out
