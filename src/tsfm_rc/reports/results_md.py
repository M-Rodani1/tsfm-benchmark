"""Generate ``RESULTS.md`` from stored artifacts only.

The report is a pure function of the files in ``results/<name>/`` (no wall-clock time, no
recomputation of statistics), so rendering twice gives byte-identical output and every
number can be traced to an artifact whose SHA-256 is listed in the Provenance section.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from tsfm_rc.config import RunConfig
from tsfm_rc.hashing import sha256_file
from tsfm_rc.provenance import read_parquet_provenance
from tsfm_rc.reports import figures

TABLES = ["dm_primary", "dm_all", "dm_per_asset", "mcs", "probabilistic", "contamination",
          "economic", "synthetic", "metrics", "windows", "data_quality", "loss_diff_series", "scales"]
LOSS_NAME = {"mse": "MSE", "qlike": "QLIKE", "mae": "MAE"}


# ------------------------------------------------------------------ formatting helpers
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


def load_tables(run_dir: Path) -> dict[str, pd.DataFrame]:
    out = {}
    for t in TABLES:
        p = run_dir / "stats" / f"{t}.parquet"
        out[t] = pd.read_parquet(p) if p.exists() else pd.DataFrame()
    return out


# ------------------------------------------------------------------ sections
def _banner(prov: dict, status: dict) -> list[str]:
    L = []
    src = prov.get("data_source", "?")
    if src == "fixture":
        L += ["> **⚠️ SYNTHETIC FIXTURE DATA.** Every number in this report was computed on simulated",
              "> series from `data/fixtures/` (GARCH/HAR processes with known parameters), not on market",
              "> data. It demonstrates that the pipeline runs and is internally consistent; it says",
              "> nothing about real markets or about the foundation models' real skill.", ""]
    else:
        L += [f"> Data source: **{src}** (raw data hash `{prov.get('raw_hash', '?')[:16]}`).", ""]
    unavailable = {m: s for m, s in status.items() if s.get("status") != "AVAILABLE"}
    if unavailable:
        L += ["> **UNAVAILABLE models** (no numbers exist for them anywhere in this report):"]
        for m, s in unavailable.items():
            L.append(f"> - `{m}`: {s.get('reason', 'unknown reason')[:220]}")
        L.append("")
    return L


def _summary(T: dict, status: dict, cfg: RunConfig) -> list[str]:
    L = ["## 1. Summary in plain English", ""]
    prim = T["dm_primary"]
    avail = prim[prim.get("status", pd.Series(dtype=str)) == "AVAILABLE"] if len(prim) else prim
    if avail.empty:
        L.append("- **Primary question (TSFMs vs baselines): no answer from this run.** None of the "
                 "pre-registered foundation models could be evaluated (see the UNAVAILABLE list above). "
                 "This is an *absent* result, not a null result.")
    else:
        better = avail[(avail["reject_holm"]) & (avail["mean_diff"] < 0)]
        worse = avail[(avail["reject_holm"]) & (avail["mean_diff"] > 0)]
        L.append(f"- **Primary family:** {len(avail)} of 27 pre-registered tests could be run. After Holm "
                 f"correction, a TSFM beat the reference baseline in **{len(better)}** and was worse in "
                 f"**{len(worse)}**; the remaining {len(avail) - len(better) - len(worse)} show no detectable difference.")
    D = T["dm_all"]
    if len(D):
        full = D[(D["period"] == "full") & (D["window"] == "expanding")]
        for kind in ("returns", "rv", "volume"):
            S = full[full["target"] == kind]
            if S.empty:
                continue
            ref = S["reference"].iloc[0]
            sig_b = S[S["reject_holm"] & (S["mean_diff"] < 0)]
            sig_w = S[S["reject_holm"] & (S["mean_diff"] > 0)]
            part = f"- **{figures.TARGET_TITLE[kind]}** (vs `{ref}`, full test period): "
            part += (f"Holm-significantly better: {', '.join(f'`{m}` h={h}' for m, h in zip(sig_b['model'], sig_b['horizon'], strict=True))}; "
                     if len(sig_b) else "no model is Holm-significantly better than the reference; ")
            part += (f"significantly worse: {', '.join(f'`{m}` h={h}' for m, h in zip(sig_w['model'], sig_w['horizon'], strict=True))}."
                     if len(sig_w) else "none significantly worse.")
            L.append(part)
    M = T["mcs"]
    if len(M):
        P = M[(M["period"] == "full") & (M["ticker"] == "POOLED")]
        for (kind, h), g in P.groupby(["target", "horizon"]):
            inc = ", ".join(f"`{m}`" for m in g.loc[g["in_mcs"], "model"])
            L.append(f"- MCS (α = {cfg.stats.mcs_alpha:.2f}, full period) for {kind} h={h}: {{{inc}}}.")
    S = T["synthetic"]
    if len(S):
        best = S[S["model"] != "oracle"].sort_values("ratio_to_oracle").groupby(["target", "horizon"]).head(1)
        txt = "; ".join(f"{r.target} h={r.horizon}: `{r.model}` ({r.ratio_to_oracle:.3f}× oracle loss)" for r in best.itertuples())
        L.append(f"- **Synthetic control** (series no model can have seen): closest to the oracle: {txt}.")
    L.append("")
    return L


def _primary(T: dict) -> list[str]:
    L = ["## 2. Pre-registered primary tests (27)", "",
         "Each TSFM vs the pre-registered reference baseline (returns: `zero`, rv: `har`, volume: `har`) on the "
         "model's own **clean** window, pooled across assets, expanding window, primary loss. Relative loss < 1 "
         "means the TSFM is better. DM-HLN two-sided p-values; Holm over the family.", ""]
    P = T["dm_primary"]
    if P.empty:
        return L + ["*(not computed)*", ""]
    rows = []
    for r in P.itertuples(index=False):
        if r.status != "AVAILABLE":
            rows.append([r.model, r.target, r.horizon, r.reference, "UNAVAILABLE", "–", "–", "–", "–", "–"])
            continue
        verdict = "TSFM better" if r.reject_holm and r.mean_diff < 0 else "TSFM worse" if r.reject_holm else "no detectable difference"
        rows.append([r.model, r.target, r.horizon, r.reference, ci(r.rel_loss, r.rel_loss_lo, r.rel_loss_hi),
                     f2(r.dm_stat), fp(r.p_value), fp(r.p_holm), int(r.T), verdict + (f" ({r.flag})" if r.flag else "")])
    df = pd.DataFrame(rows, columns=["model", "target", "h", "reference", "rel. loss [95% CI]", "DM", "p", "Holm p", "T", "verdict"])
    return L + [md_table(df)]


def _survival(T: dict, cfg: RunConfig) -> list[str]:
    L = ["## 3. Which conclusions survive multiple-testing correction", "",
         "A conclusion is listed as *surviving* only if its Holm-adjusted p-value is below "
         f"{cfg.stats.alpha:.2f} within its pre-specified family. Everything that was significant only before "
         "correction is listed separately and should **not** be reported as a finding.", ""]
    fams = []
    if len(T["dm_primary"]):
        fams.append(("Primary (TSFM vs reference, clean windows)", T["dm_primary"].dropna(subset=["p_value"])))
    D = T["dm_all"]
    for (period, window), g in (D.groupby(["period", "window"]) if len(D) else []):
        fams.append((f"All models vs reference · {period} · {window} window", g))
    PA = T["dm_per_asset"]
    for period, g in (PA.groupby("period") if len(PA) else []):
        fams.append((f"Per-asset tests · {period}", g))
    PR = T["probabilistic"]
    if len(PR) and "p_value" in PR:
        for period, g in PR.dropna(subset=["p_value"]).groupby("period"):
            fams.append((f"Probabilistic h=1 (CRPS) · {period}", g))
    summ = []
    survivors, casualties = [], []
    for name, g in fams:
        if g.empty:
            continue
        raw = int((g["p_value"] < cfg.stats.alpha).sum())
        adj = int(g["reject_holm"].astype(bool).sum())
        summ.append([name, len(g), raw, adj])
        for r in g.itertuples(index=False):
            tag = f"`{r.model}` vs `{r.reference}` · {r.target} h={r.horizon}" + (f" · {r.ticker}" if hasattr(r, "ticker") else "")
            direction = "better" if r.mean_diff < 0 else "worse"
            if bool(r.reject_holm):
                survivors.append(f"- {name}: {tag}: model **{direction}** (p = {fp(r.p_value)}, Holm p = {fp(r.p_holm)})")
            elif r.p_value < cfg.stats.alpha:
                casualties.append(f"- {name}: {tag}: {direction} at raw p = {fp(r.p_value)}, but Holm p = {fp(r.p_holm)}")
    L.append(md_table(pd.DataFrame(summ, columns=["family", "tests", "raw p < α", "Holm-significant"])))
    L += ["**Survives correction:**", ""] + (survivors[:60] or ["- nothing"])
    if len(survivors) > 60:
        L.append(f"- … and {len(survivors) - 60} more (see `stats/dm_*.parquet`).")
    L += ["", "**Significant before correction only (do not report as findings):**", ""] + (casualties[:40] or ["- nothing"])
    if len(casualties) > 40:
        L.append(f"- … and {len(casualties) - 40} more.")
    C = T["contamination"]
    if len(C) and "reject_holm" in C:
        mem = C[C.get("memorisation_evidence", False) == True]  # noqa: E712
        L += ["", f"**Contamination tests surviving Holm and exceeding the placebo:** {len(mem)}."]
    L.append("")
    return L


def _secondary(T: dict, fig_links: dict) -> list[str]:
    L = ["## 4. All models vs reference (secondary)", "",
         "Pooled relative loss with 95% stationary-bootstrap CI. `full` = whole test period (possibly "
         "contaminated for TSFMs); `common_clean` = after the latest TSFM release + 30 days.", ""]
    for key in ("relative_loss_full", "relative_loss_clean"):
        for p in fig_links.get(key, []):
            if p.endswith(".png"):
                L.append(f"![{key}]({p})")
    L.append("")
    D = T["dm_all"]
    if D.empty:
        return L + ["*(not computed)*", ""]
    for period in ("full", "common_clean"):
        S = D[(D["period"] == period) & (D["window"] == "expanding")].sort_values(["target", "horizon", "model"])
        if S.empty:
            continue
        rows = [[r.target, r.horizon, r.model, r.reference, LOSS_NAME.get(r.loss, r.loss), ci(r.rel_loss, r.rel_loss_lo, r.rel_loss_hi),
                 f2(r.dm_stat), fp(r.p_value), fp(r.p_holm), int(r.T), r.flag or ""] for r in S.itertuples(index=False)]
        L += [f"### {period} · expanding window", "",
              md_table(pd.DataFrame(rows, columns=["target", "h", "model", "reference", "loss", "rel. loss [95% CI]", "DM", "p", "Holm p", "T", "flags"]))]
    return L


def _rolling(T: dict) -> list[str]:
    L = ["## 5. Robustness: rolling vs expanding window (baselines)", ""]
    D = T["dm_all"]
    if D.empty or "rolling" not in set(D["window"]):
        return L + ["*(rolling window not run)*", ""]
    a = D[(D["period"] == "full") & (D["window"] == "expanding")].set_index(["target", "horizon", "model"])
    b = D[(D["period"] == "full") & (D["window"] == "rolling")].set_index(["target", "horizon", "model"])
    j = a[["rel_loss", "reject_holm"]].join(b[["rel_loss", "reject_holm"]], lsuffix="_exp", rsuffix="_roll", how="inner")
    flips = j[(j["reject_holm_exp"] != j["reject_holm_roll"]) | ((j["rel_loss_exp"] < 1) != (j["rel_loss_roll"] < 1))]
    L.append(f"{len(j)} model/target/horizon comparisons exist in both variants; in **{len(flips)}** the direction "
             "(relative loss above/below 1) or Holm significance differs between the expanding and the rolling window.")
    if len(flips):
        rows = [[t, h, m, f3(r.rel_loss_exp), bool(r.reject_holm_exp), f3(r.rel_loss_roll), bool(r.reject_holm_roll)]
                for (t, h, m), r in flips.iterrows()]
        L += ["", md_table(pd.DataFrame(rows, columns=["target", "h", "model", "rel. loss (expanding)", "Holm sig.", "rel. loss (rolling)", "Holm sig."]))]
    L.append("")
    return L


def _mcs(T: dict, fig_links: dict, cfg: RunConfig) -> list[str]:
    L = ["## 6. Model Confidence Sets", "",
         f"Hansen–Lunde–Nason MCS, T_max statistic, α = {cfg.stats.mcs_alpha:.2f}, stationary bootstrap "
         f"(B = {cfg.stats.n_bootstrap}), pooled normalised primary loss on (asset, origin) pairs where every model has a forecast.", ""]
    for key in ("mcs_full", "mcs_clean"):
        for p in fig_links.get(key, []):
            if p.endswith(".png"):
                L.append(f"![{key}]({p})")
    M = T["mcs"]
    if M.empty:
        return L + ["", "*(not computed)*", ""]
    P = M[M["ticker"] == "POOLED"].sort_values(["period", "target", "horizon", "mcs_pvalue"], ascending=[True, True, True, False])
    rows = [[r.period, r.target, r.horizon, r.model, f3(r.mean_loss), fp(r.mcs_pvalue), "yes" if r.in_mcs else "no", int(r.T)]
            for r in P.itertuples(index=False)]
    return L + ["", md_table(pd.DataFrame(rows, columns=["period", "target", "h", "model", "mean norm. loss", "MCS p", "in MCS", "T"]))]


def _prob(T: dict) -> list[str]:
    L = ["## 7. Probabilistic forecasts (h = 1)", "",
         "CRPS approximated from the nine deciles (DECISIONS D-012), normalised by the pre-test standard "
         "deviation; reference: returns → `hist_mean`, rv → `har`, volume → `har`.", ""]
    P = T["probabilistic"]
    if P.empty:
        return L + ["*(no model produced quantiles)*", ""]
    rows = [[r.period, r.target, r.model, f3(r.crps_n), fp(getattr(r, "p_value", np.nan)), fp(getattr(r, "p_holm", np.nan))]
            for r in P.sort_values(["period", "target", "crps_n"]).itertuples(index=False)]
    return L + [md_table(pd.DataFrame(rows, columns=["period", "target", "model", "mean CRPS (norm.)", "p vs ref", "Holm p"]))]


def _contamination(T: dict, fig_links: dict) -> list[str]:
    L = ["## 8. Contamination control", "",
         "Δ = ln R_clean − ln R_seen with R = (TSFM loss)/(reference loss); Δ > 0 would be consistent with "
         "memorisation. Placebo rows apply the same statistic to baselines that cannot memorise, on the same "
         "windows, to show how much market-regime differences alone move Δ.", ""]
    W = T["windows"]
    if len(W):
        L += [md_table(W[["model", "release_date", "weights_date", "effective_release", "clean_start", "common_clean_start"]].astype(str))]
    for p in fig_links.get("contamination", []):
        if p.endswith(".png"):
            L.append(f"![contamination]({p})")
    C = T["contamination"]
    if C.empty or "delta" not in C:
        return L + ["", "*(not computed)*", ""]
    rows = []
    for r in C.sort_values(["windows_of", "target", "horizon", "role"]).itertuples(index=False):
        if r.status != "AVAILABLE":
            rows.append([r.windows_of, r.role, r.model, r.target, r.horizon, "UNAVAILABLE", "–", "–", "–", "–"])
            continue
        rows.append([r.windows_of, r.role, r.model, r.target, r.horizon, f3(r.delta), f"[{f3(r.ci_lo)}, {f3(r.ci_hi)}]",
                     fp(r.p_one_sided), fp(r.p_holm) if r.role == "tsfm" else "–", f"{int(r.T_seen)}/{int(r.T_clean)}"])
    L += ["", md_table(pd.DataFrame(rows, columns=["windows of", "role", "model", "target", "h", "Δ", "95% CI", "p (Δ>0)", "Holm p", "T seen/clean"]))]
    pl = C[(C["role"] == "placebo") & C["delta"].notna()]
    if len(pl):
        L.append(f"Placebo Δ ranged from {pl['delta'].min():.3f} to {pl['delta'].max():.3f}; "
                 f"{int(((pl['ci_lo'] > 0) | (pl['ci_hi'] < 0)).sum())} of {len(pl)} placebo CIs exclude 0, "
                 "which shows how easily the seen/clean comparison moves without any memorisation.")
    L.append("")
    return L


def _synthetic(T: dict, fig_links: dict, meta: dict) -> list[str]:
    L = ["## 9. Synthetic control", "",
         f"{meta.get('n_series', '?')} simulated series (GARCH(1,1) and HAR-type variance, calibrated on "
         f"`{meta.get('calibration_asset', '?')}`), {meta.get('test_days', '?')} test days each. The oracle knows the "
         "true conditional expectation. Ratios > 1 = worse than optimal. The oracle is optimal *in expectation*, so "
         "in a finite sample a model can land slightly below 1 by chance; the DM p-value against the oracle says "
         "whether a gap is distinguishable from noise.", ""]
    for p in fig_links.get("synthetic", []):
        if p.endswith(".png"):
            L.append(f"![synthetic]({p})")
    S = T["synthetic"]
    if S.empty:
        return L + ["*(not run)*", ""]
    rows = [[r.target, r.horizon, r.model, LOSS_NAME.get(r.loss, r.loss), f3(r.mean_loss), f3(r.ratio_to_oracle),
             f3(getattr(r, "ratio_to_oracle_latent", np.nan)), fp(r.dm_vs_oracle_p)]
            for r in S.sort_values(["target", "horizon", "ratio_to_oracle"]).itertuples(index=False)]
    return L + ["", md_table(pd.DataFrame(rows, columns=["target", "h", "model", "loss", "mean loss", "× oracle (proxy)", "× oracle (latent)", "DM p vs oracle"]))]


def _economic(T: dict, cfg: RunConfig) -> list[str]:
    L = ["## 10. Economic evaluation (illustrative only; not a trading claim)", "",
         f"Volatility targeting on `{cfg.economic.asset}`: weight = min({cfg.economic.max_leverage}, "
         f"{cfg.economic.target_vol_annual:.0%} / forecast vol) from the h={cfg.economic.horizon} volatility forecast, "
         f"rebalanced at each origin, {cfg.economic.cost_bps:g} bp per unit turnover, cash earns 0. All models are evaluated "
         "on the same dates. Because the GK target omits overnight moves, realised volatility sits above target for all models.", ""]
    E = T["economic"]
    if E.empty:
        return L + ["*(not run)*", ""]
    rows = [[r.period, r.model, f3(r.ann_return), f3(r.ann_vol), f2(r.sharpe), f3(r.max_drawdown), f2(getattr(r, "avg_weight", np.nan)),
             f2(getattr(r, "turnover_per_year", np.nan))] for r in E.sort_values(["period", "model"]).itertuples(index=False)]
    return L + [md_table(pd.DataFrame(rows, columns=["period", "model", "ann. return", "ann. vol", "Sharpe", "max DD", "avg weight", "turnover/yr"]))]


def _data(run_dir: Path, T: dict) -> list[str]:
    L = ["## 11. Data and cleaning", ""]
    cr = run_dir / "cleaning_report.csv"
    if cr.exists():
        c = pd.read_csv(cr)
        if len(c):
            s = c.groupby(["issue", "action"]).size().rename("count").reset_index()
            L += ["Every data adjustment is listed row by row in `cleaning_report.csv`. Summary:", "", md_table(s)]
        else:
            L += ["No cleaning events.", ""]
    dq = T["data_quality"]
    if len(dq):
        L += ["Forecast rows without a realised target (end of sample or missing inputs), excluded from evaluation:", "",
              md_table(dq)]
    return L


def _limitations(T: dict, prov: dict, status: dict) -> list[str]:
    L = ["## 12. Limitations", ""]
    if prov.get("data_source") == "fixture":
        L.append("- **Synthetic data.** This run uses simulated fixtures; nothing here generalises to markets.")
    if any(s.get("status") != "AVAILABLE" for s in status.values()):
        L.append("- **Missing models.** At least one TSFM was UNAVAILABLE, so the primary question is only partly (or not) answered.")
    D = T["dm_all"]
    n_small = int(D["flag"].fillna("").str.contains("small_sample").sum()) if len(D) else 0
    if n_small:
        L.append(f"- **Small samples.** {n_small} tests use fewer than 100 origins; the simulation behind amendment A2 shows "
                 "DM-HLN over-rejects somewhat at T≈50, so treat marginal p-values there with caution.")
    L += [
        "- **Survivorship bias.** The stock list conditions on firms that are large in 2026 (DECISIONS D-003).",
        "- **Volatility proxy.** Garman–Klass measures open-to-close variance; overnight moves are excluded for every model.",
        "- **Pretraining corpora are only partly documented.** See the verification tags in `docs/PRETRAINING-DATA.md`; "
        "a null contamination result is not proof that the models never saw these series.",
        "- **Regime confounding.** Seen and clean windows are different market periods; the placebo only partly controls for this.",
        "- **Amendments.** The design was amended three times before any real-data result existed (A1–A3 in "
        "`docs/PREREGISTRATION.md`).",
        "- **Economic evaluation** is a single illustrative strategy with no significance testing.",
        "",
    ]
    return L


def _provenance(run_dir: Path, prov: dict, cfg_hash: str) -> list[str]:
    L = ["## 13. Provenance", "",
         f"- Config: `{prov.get('config_name')}` · config hash `{cfg_hash}`",
         f"- Cleaned-panel hash `{prov.get('data_hash', '?')}` · raw-data hash `{prov.get('raw_hash', '?')}`",
         f"- Git commit `{prov.get('git', {}).get('commit', '?')}` (working tree dirty: {prov.get('git', {}).get('dirty')})",
         f"- Statistics computed (UTC): {prov.get('created_utc', '?')}",
         "- Packages: " + ", ".join(f"{k} {v}" for k, v in sorted(prov.get("packages", {}).items()) if v != "not-installed"),
         "", "Artifacts (every number above is read from these files):", ""]
    rows = []
    for p in sorted(run_dir.rglob("*")):
        if p.is_file() and p.suffix in (".parquet", ".json", ".csv"):
            rows.append([str(p.relative_to(run_dir.parent.parent)), sha256_file(p)[:16]])
    L += [md_table(pd.DataFrame(rows, columns=["file", "sha256 (first 16)"]))]
    return L


# ------------------------------------------------------------------ driver
def render(cfg: RunConfig, run_dir: Path, report_dir: Path, *, make_figures: bool = True) -> str:
    from tsfm_rc.config import config_hash

    T = load_tables(run_dir)
    prov = read_parquet_provenance(run_dir / "stats" / "dm_all.parquet") if (run_dir / "stats" / "dm_all.parquet").exists() else {}
    status = json.loads((run_dir / "model_status.json").read_text()) if (run_dir / "model_status.json").exists() else {}
    meta = json.loads((run_dir / "synthetic_meta.json").read_text()) if (run_dir / "synthetic_meta.json").exists() else {}
    fig_links = {}
    if make_figures:
        fig_paths = figures.make_all(T, report_dir / "figures")
        fig_links = {k: [str(Path(p).relative_to(report_dir)) for p in v] for k, v in fig_paths.items()}
    title = f"# Results: `{cfg.name}`"
    out = [title, "",
           f"Generated by `tsfm-rc report` from the artifacts in `results/{cfg.name}/`. Nothing in this file is typed by "
           "hand: every number is read from a stored table whose SHA-256 is listed under Provenance, and "
           "rendering again from the same artifacts gives an identical file.", ""]
    out += _banner(prov, status)
    out += _summary(T, status, cfg)
    out += _primary(T)
    out += _survival(T, cfg)
    out += _secondary(T, fig_links)
    out += _rolling(T)
    out += _mcs(T, fig_links, cfg)
    out += _prob(T)
    out += _contamination(T, fig_links)
    out += _synthetic(T, fig_links, meta)
    out += _economic(T, cfg)
    out += _data(run_dir, T)
    out += _limitations(T, prov, status)
    out += _provenance(run_dir, prov, config_hash(cfg))
    return "\n".join(out).rstrip() + "\n"


def write_report(cfg: RunConfig, run_dir: Path, report_root: Path) -> Path:
    report_dir = report_root / cfg.name
    report_dir.mkdir(parents=True, exist_ok=True)
    text = render(cfg, run_dir, report_dir)
    path = report_dir / "RESULTS.md"
    path.write_text(text, encoding="utf-8")
    return path


def write_index(report_root: Path) -> Path:
    """``reports/RESULTS.md``: the most authoritative available report, clearly labelled."""
    order = ["default", "default_fixtures", "smoke"]
    available = [n for n in order if (report_root / n / "RESULTS.md").exists()]
    lines = ["# RESULTS", ""]
    if not available:
        lines.append("No results yet. Run `make smoke` (offline) or `make reproduce` (network).")
    else:
        main = available[0]
        lines += [
            f"This page shows the report of the **`{main}`** run, the most complete run available in this checkout "
            "(preference: `default` (real data) > `default_fixtures` > `smoke`).",
            "",
            "Other reports: " + ", ".join(f"[`{n}`]({n}/RESULTS.md)" for n in available) + ".",
            "",
            "---",
            "",
        ]
        body = (report_root / main / "RESULTS.md").read_text(encoding="utf-8")
        body = body.replace("](figures/", f"]({main}/figures/")
        lines.append(body)
    path = report_root / "RESULTS.md"
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path
