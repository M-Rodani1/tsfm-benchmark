"""Turn stored forecasts into every table of the pre-registered analysis.

Input: the long forecast table (baselines + TSFMs), the panel, the config and the TSFM
status. Output: a dict of DataFrames, each saved as Parquet with provenance by the runner.

Tables
------
losses            row-level losses (raw and normalised) with window labels
metrics           mean losses, OOS R^2, directional accuracy (per asset and pooled)
losses_primary    row-level losses of the stride-1 primary pass (amendment A4)
dm_primary        the 27 pre-registered tests (TSFM vs reference, stride-1 origins in the
                  model's clean window, Kiefer-Vogelsang fixed-b test; A4), Holm
dm_all            every model vs reference, per window variant and evaluation period, Holm
dm_per_asset      per-asset tests, Holm within family
mcs               Model Confidence Sets (pooled and per asset)
probabilistic     h=1 CRPS (quantile approximation) and DM vs probabilistic reference
contamination     seen (stride 5) vs clean (stride 1, A4) Delta per TSFM and placebo pairs,
                  Holm over TSFM tests
economic          volatility-targeting backtest (illustrative)
loss_diff_series  pooled loss differential per origin (for the dashboard's time plot)
synthetic         synthetic-control losses relative to the oracle
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from tsfm_rc.config import RunConfig
from tsfm_rc.contamination.windows import common_clean_start, windows_for_models
from tsfm_rc.engine.walkforward import qcol
from tsfm_rc.eval.bootstrap import block_length
from tsfm_rc.eval.contamination_test import contamination_delta
from tsfm_rc.eval.dm import dm_test, h_eff_for, overlap_order
from tsfm_rc.eval.economic import backtest, buy_and_hold
from tsfm_rc.eval.mcs import model_confidence_set
from tsfm_rc.eval.metrics import (
    PRIMARY_LOSS,
    absolute_error,
    crps_from_quantiles,
    directional_hit,
    oos_r2,
    pinball,
    qlike,
    squared_error,
)
from tsfm_rc.eval.multiple import holm
from tsfm_rc.eval.pooled import paired_pooled, pooled_matrix, pretest_scales, ratio_ci
from tsfm_rc.eval.size_study import kv_simulated_size
from tsfm_rc.seeding import derive_seed

log = logging.getLogger(__name__)

PROB_REFERENCE = {"returns": "hist_mean", "rv": "har", "volume": "har"}
SMALL_SAMPLE_T = 100


# ------------------------------------------------------------------ losses
def add_losses(fc: pd.DataFrame, cfg: RunConfig, scales: pd.DataFrame) -> pd.DataFrame:
    levels = cfg.stats.quantile_levels
    L = fc[fc["y_true"].notna()].copy()
    y, f = L["y_true"].to_numpy(), L["y_pred"].to_numpy()
    L["mse"] = squared_error(y, f)
    L["mae"] = absolute_error(y, f)
    L["qlike"] = np.where(L["target"] == "rv", qlike(y, f), np.nan)
    L["dir_hit"] = np.where(L["target"] == "returns", directional_hit(y, f), np.nan)
    qc = [qcol(q) for q in levels]
    L["crps"] = np.nan
    if all(c in L.columns for c in qc):
        has_q = L[qc].notna().all(axis=1) & (L["horizon"] == 1)
        if has_q.any():
            L.loc[has_q, "crps"] = crps_from_quantiles(L.loc[has_q, "y_true"].to_numpy(), L.loc[has_q, qc].to_numpy(), levels)
            for tau in (0.1, 0.5, 0.9):  # pinball losses reported on their own (PREREGISTRATION s.6)
                if tau in levels:
                    L[f"pinball_{qcol(tau)}"] = np.nan
                    L.loc[has_q, f"pinball_{qcol(tau)}"] = pinball(L.loc[has_q, "y_true"].to_numpy(), L.loc[has_q, qcol(tau)].to_numpy(), tau)
    if len(scales):
        sc = scales.pivot_table(index=["ticker", "target", "horizon"], columns="loss", values="scale").reset_index()
        sc.columns = [c if c in ("ticker", "target", "horizon") else f"scale_{c}" for c in sc.columns]
        L = L.merge(sc, on=["ticker", "target", "horizon"], how="left")
    for loss in ("mse", "mae", "crps"):
        L[f"{loss}_n"] = L[loss] / L.get(f"scale_{loss}", np.nan)
    L["qlike_n"] = L["qlike"]
    return L


def add_window_labels(L: pd.DataFrame, cfg: RunConfig, status: dict) -> tuple[pd.DataFrame, dict, pd.Timestamp]:
    windows = windows_for_models(cfg, status)
    available = [m for m, s in status.items() if s.get("status") == "AVAILABLE"]
    ccs = common_clean_start(windows, available)
    for name, w in windows.items():
        L[f"win_{name}"] = w.label(L["origin"], L["label_end"]).to_numpy()
    L["common_clean"] = (L["origin"] >= ccs) if ccs is not None else False
    return L, windows, ccs


def _period_mask(L: pd.DataFrame, period: str) -> pd.Series:
    if period == "full":
        return pd.Series(True, index=L.index)
    if period == "common_clean":
        return L["common_clean"].astype(bool)
    kind, model = period.split(":", 1)  # "clean:<model>" or "seen:<model>"
    return L[f"win_{model}"] == kind


# ------------------------------------------------------------------ tables
def metrics_table(L: pd.DataFrame, cfg: RunConfig, periods: list[str]) -> pd.DataFrame:
    rows = []
    for period in periods:
        P = L[_period_mask(L, period)]
        for (kind, h, window), G in P.groupby(["target", "horizon", "window"]):
            bench = cfg.models.r2_benchmark[kind]
            B = G[G["model"] == bench].set_index(["ticker", "origin"])["y_pred"]
            for model, M in G.groupby("model"):
                for scope, S in [("POOLED", M), *M.groupby("ticker")]:
                    j = S.set_index(["ticker", "origin"]).join(B.rename("bench"), how="inner")
                    rows.append({
                        "period": period, "target": kind, "horizon": h, "window": window, "model": model,
                        "ticker": scope, "n": len(S),
                        "mse": S["mse"].mean(), "mae": S["mae"].mean(),
                        "qlike": S["qlike"].mean() if kind == "rv" else np.nan,
                        "mse_n": S["mse_n"].mean(), "mae_n": S["mae_n"].mean(),
                        "dir_acc": S["dir_hit"].mean() if kind == "returns" else np.nan,
                        "crps": S["crps"].mean() if h == 1 else np.nan,
                        "oos_r2": oos_r2(j["y_true"], j["y_pred"], j["bench"]) if len(j) else np.nan,
                        "r2_benchmark": bench,
                    })
    return pd.DataFrame(rows)


def _dm_row(pp: pd.DataFrame, h: int, cfg: RunConfig, seed_keys: tuple, *, stride: int | None = None,
            method: str = "hln") -> dict:
    """DM test + relative loss with bootstrap CI. ``stride`` is the spacing of the origins in
    ``pp`` (default: the main schedule); it sets h_eff for the variance rule and the block
    length, so overlapping targets are handled the same way in the test and in the CI."""
    stride = cfg.evaluation.stride if stride is None else stride
    h_eff = h_eff_for(h, stride)
    d = (pp["m"] - pp["ref"]).to_numpy()
    r = dm_test(d, h_eff=h_eff, method=method)
    rng = np.random.default_rng(derive_seed(cfg.seed, *seed_keys))
    ratio, lo, hi = ratio_ci(pp["m"].to_numpy(), pp["ref"].to_numpy(), cfg.stats.n_bootstrap, block_length(len(pp), h_eff), rng)
    flags = [f for f in (r.flag, "small_sample" if r.T < SMALL_SAMPLE_T else "") if f]
    return {
        "dm_stat": r.stat, "p_value": r.pvalue, "mean_diff": r.mean_diff, "T": r.T, "lag": r.lag,
        "h_eff": h_eff, "rel_loss": ratio, "rel_loss_lo": lo, "rel_loss_hi": hi,
        "mean_assets": float(pp["n_assets"].mean()) if len(pp) else np.nan,
        "start": pp.index.min() if len(pp) else pd.NaT, "end": pp.index.max() if len(pp) else pd.NaT,
        "flag": ";".join(flags),
    }


def dm_primary(LP: pd.DataFrame | None, cfg: RunConfig, status: dict) -> pd.DataFrame:
    """The 27 confirmatory tests on the stride-1 primary pass (amendment A4).

    ``LP`` holds the losses of the primary pass only (stride ``primary_stride`` origins); the
    main stride-5 losses are never used here. Test: Kiefer-Vogelsang fixed-b (bandwidth T),
    h_eff = h at stride 1 for the block length of the relative-loss CI.
    """
    stride = cfg.evaluation.primary_stride
    rows = []
    for spec in cfg.models.tsfms:
        m = spec.name
        avail = status.get(m, {}).get("status") == "AVAILABLE"
        for kind in cfg.targets.kinds:
            ref = cfg.models.reference[kind]
            loss = PRIMARY_LOSS[kind]
            for h in cfg.targets.horizons:
                base = {"model": m, "target": kind, "horizon": h, "reference": ref, "loss": loss,
                        "period": f"clean:{m}", "status": "AVAILABLE" if avail else "UNAVAILABLE",
                        "stride": stride, "method": "kv_b1"}
                if not avail:
                    rows.append({**base, "p_value": np.nan, "flag": status.get(m, {}).get("reason", "")[:200]})
                    continue
                if LP is None or LP.empty:
                    rows.append({**base, "p_value": np.nan, "T": 0, "flag": "no_primary_pass_forecasts"})
                    continue
                S = LP[(LP["target"] == kind) & (LP["horizon"] == h) & (LP["window"] == cfg.evaluation.primary_window)
                       & (LP[f"win_{m}"] == "clean")]
                pp = paired_pooled(S, m, ref, f"{loss}_n")
                row = {**base, **_dm_row(pp, h, cfg, ("dm_primary", m, kind, h), stride=stride, method="kv_b1")}
                row["sim_size_max"] = kv_simulated_size(int(row["T"]), h)
                rows.append(row)
    df = pd.DataFrame(rows)
    df["p_holm"], df["reject_holm"] = holm(df["p_value"].to_numpy(), cfg.stats.alpha)
    df["tsfm_better"] = df["reject_holm"] & (df.get("mean_diff", pd.Series(np.nan, index=df.index)) < 0)
    return df


def diff_series(L: pd.DataFrame, cfg: RunConfig) -> pd.DataFrame:
    """Loss differential (model - reference, primary loss) per origin, full test period.

    Pooled (normalised, cross-sectional mean) for every window variant, and per asset
    (raw primary loss) for the expanding window. ``cum_diff`` is the running sum, stored so
    that the dashboard only plots stored numbers.
    """
    parts = []
    for window in cfg.evaluation.windows:
        for kind in cfg.targets.kinds:
            ref = cfg.models.reference[kind]
            loss = PRIMARY_LOSS[kind]
            for h in cfg.targets.horizons:
                S = L[(L["target"] == kind) & (L["horizon"] == h) & (L["window"] == window)]
                for m in sorted(set(S["model"]) - {ref}):
                    scopes = [("POOLED", S, f"{loss}_n")]
                    if window == "expanding":
                        scopes += [(t, St, loss) for t, St in S.groupby("ticker")]
                    for scope, Ss, col in scopes:
                        pp = paired_pooled(Ss, m, ref, col)
                        if len(pp) < 2:
                            continue
                        d = (pp["m"] - pp["ref"]).to_numpy()
                        parts.append(pd.DataFrame({
                            "target": kind, "horizon": h, "window": window, "model": m, "reference": ref,
                            "ticker": scope, "origin": pp.index, "diff": d, "cum_diff": np.cumsum(d),
                            "n_assets": pp["n_assets"].to_numpy(),
                        }))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def dm_all(L: pd.DataFrame, cfg: RunConfig, periods: list[str]) -> pd.DataFrame:
    rows = []
    for period in periods:
        P = L[_period_mask(L, period)]
        for window in cfg.evaluation.windows:
            fam = []
            for kind in cfg.targets.kinds:
                ref = cfg.models.reference[kind]
                loss = PRIMARY_LOSS[kind]
                for h in cfg.targets.horizons:
                    S = P[(P["target"] == kind) & (P["horizon"] == h) & (P["window"] == window)]
                    for m in sorted(set(S["model"]) - {ref}):
                        pp = paired_pooled(S, m, ref, f"{loss}_n")
                        if len(pp) < 3:
                            continue
                        fam.append({"period": period, "window": window, "target": kind, "horizon": h, "model": m,
                                    "reference": ref, "loss": loss, **_dm_row(pp, h, cfg, ("dm_all", period, window, m, kind, h))})
            if fam:
                f = pd.DataFrame(fam)
                f["p_holm"], f["reject_holm"] = holm(f["p_value"].to_numpy(), cfg.stats.alpha)
                rows.append(f)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def dm_per_asset(L: pd.DataFrame, cfg: RunConfig, status: dict) -> pd.DataFrame:
    rows = []
    specs = [("common_clean", None)] + [(f"clean:{s.name}", s.name) for s in cfg.models.tsfms
                                         if status.get(s.name, {}).get("status") == "AVAILABLE"]
    for period, only in specs:
        P = L[_period_mask(L, period) & (L["window"] == "expanding")]
        for kind in cfg.targets.kinds:
            ref = cfg.models.reference[kind]
            loss = PRIMARY_LOSS[kind]
            for h in cfg.targets.horizons:
                S = P[(P["target"] == kind) & (P["horizon"] == h)]
                models = [only] if only else sorted(set(S["model"]) - {ref})
                for m in models:
                    for t, St in S.groupby("ticker"):
                        pp = paired_pooled(St, m, ref, loss)
                        if len(pp) < 3:
                            continue
                        h_eff = overlap_order(h, cfg.evaluation.stride) + 1
                        r = dm_test((pp["m"] - pp["ref"]).to_numpy(), h_eff=h_eff)
                        rows.append({"period": period, "target": kind, "horizon": h, "model": m, "reference": ref,
                                     "ticker": t, "loss": loss, "dm_stat": r.stat, "p_value": r.pvalue,
                                     "mean_diff": r.mean_diff, "T": r.T, "rel_loss": pp["m"].mean() / pp["ref"].mean(),
                                     "flag": r.flag})
    df = pd.DataFrame(rows)
    if len(df):
        df["p_holm"] = np.nan
        df["reject_holm"] = False
        for _, idx in df.groupby("period").groups.items():
            adj, rej = holm(df.loc[idx, "p_value"].to_numpy(), cfg.stats.alpha)
            df.loc[idx, "p_holm"] = adj
            df.loc[idx, "reject_holm"] = rej
    return df


def mcs_table(L: pd.DataFrame, cfg: RunConfig, periods: list[str]) -> pd.DataFrame:
    rows = []
    for period in periods:
        P = L[_period_mask(L, period) & (L["window"] == "expanding")]
        for kind in cfg.targets.kinds:
            loss = f"{PRIMARY_LOSS[kind]}_n"
            for h in cfg.targets.horizons:
                S = P[(P["target"] == kind) & (P["horizon"] == h)]
                models = sorted(S["model"].unique())
                scopes = [("POOLED", S)] + (list(S.groupby("ticker")) if period == "common_clean" else [])
                for scope, Ss in scopes:
                    M = pooled_matrix(Ss, models, loss)
                    if M.shape[0] < 10 or M.shape[1] < 2:
                        continue
                    h_eff = overlap_order(h, cfg.evaluation.stride) + 1
                    rng = np.random.default_rng(derive_seed(cfg.seed, "mcs", period, kind, h, scope))
                    res = model_confidence_set(M, cfg.stats.mcs_alpha, B=cfg.stats.n_bootstrap,
                                               block=block_length(len(M), h_eff), statistic=cfg.stats.mcs_statistic, rng=rng)
                    t = res.table()
                    t["mean_loss"] = t["model"].map(M.mean())
                    t = t.assign(period=period, target=kind, horizon=h, ticker=scope, T=len(M), loss=loss)
                    rows.append(t)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def probabilistic_table(L: pd.DataFrame, cfg: RunConfig, periods: list[str]) -> pd.DataFrame:
    rows = []
    for period in periods:
        P = L[_period_mask(L, period) & (L["window"] == "expanding") & (L["horizon"] == 1) & L["crps_n"].notna()]
        fam = []
        for kind in cfg.targets.kinds:
            ref = PROB_REFERENCE[kind]
            S = P[P["target"] == kind]
            for m in sorted(S["model"].unique()):
                Sm = S[S["model"] == m]
                row = {"period": period, "target": kind, "horizon": 1, "model": m, "reference": ref,
                       "crps_n": Sm["crps_n"].mean(), "crps": Sm["crps"].mean(),
                       **{c: Sm[c].mean() for c in Sm.columns if c.startswith("pinball_")}}
                if m != ref and ref in set(S["model"]):
                    pp = paired_pooled(S, m, ref, "crps_n")
                    if len(pp) >= 3:
                        row.update(_dm_row(pp, 1, cfg, ("prob", period, kind, m)))
                fam.append(row)
        if fam:
            f = pd.DataFrame(fam)
            f["p_holm"], f["reject_holm"] = holm(f.get("p_value", pd.Series(np.nan, index=f.index)).to_numpy(), cfg.stats.alpha)
            rows.append(f)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def contamination_table(L: pd.DataFrame, LP: pd.DataFrame | None, cfg: RunConfig, status: dict) -> pd.DataFrame:
    """Seen side from the main stride-5 pass ``L``; clean side from the stride-1 primary pass
    ``LP`` (amendment A4). Each side's bootstrap block length uses its own h_eff."""
    LP = LP if LP is not None else L.iloc[0:0]
    rows = []
    for spec in cfg.models.tsfms:
        w = spec.name
        avail = status.get(w, {}).get("status") == "AVAILABLE"
        for kind in cfg.targets.kinds:
            ref = cfg.models.reference[kind]
            loss = f"{PRIMARY_LOSS[kind]}_n"
            candidates = ([(w, "tsfm")] if avail else []) + [(b, "placebo") for b in cfg.contamination.placebo_pairs.get(kind, [])]
            for h in cfg.targets.horizons:
                S = L[(L["target"] == kind) & (L["horizon"] == h) & (L["window"] == "expanding")]
                SP = LP[(LP["target"] == kind) & (LP["horizon"] == h) & (LP["window"] == "expanding")] if len(LP) else LP
                h_eff = h_eff_for(h, cfg.evaluation.stride)
                h_eff_clean = h_eff_for(h, cfg.evaluation.primary_stride)
                if not avail:
                    rows.append({"windows_of": w, "model": w, "role": "tsfm", "target": kind, "horizon": h,
                                 "reference": ref, "status": "UNAVAILABLE"})
                for m, role in candidates:
                    seen = paired_pooled(S[S[f"win_{w}"] == "seen"], m, ref, loss)
                    clean = (paired_pooled(SP[SP[f"win_{w}"] == "clean"], m, ref, loss) if len(SP)
                             else pd.DataFrame(columns=["m", "ref", "n_assets"]))
                    rng = np.random.default_rng(derive_seed(cfg.seed, "contam", w, m, kind, h))
                    res = contamination_delta(seen["m"], seen["ref"], clean["m"], clean["ref"],
                                              B=cfg.stats.n_bootstrap, h_eff=h_eff, h_eff_clean=h_eff_clean, rng=rng)
                    rows.append({"windows_of": w, "model": m, "role": role, "target": kind, "horizon": h,
                                 "reference": ref, "status": "AVAILABLE", **res})
    df = pd.DataFrame(rows)
    if "p_one_sided" not in df.columns:
        df["p_one_sided"] = np.nan
    df["p_holm"] = np.nan
    df["reject_holm"] = False
    tsfm_rows = df["role"] == "tsfm"
    adj, rej = holm(df.loc[tsfm_rows, "p_one_sided"].to_numpy(), cfg.stats.alpha)
    df.loc[tsfm_rows, "p_holm"] = adj
    df.loc[tsfm_rows, "reject_holm"] = rej
    # "consistent with memorisation" requires Holm significance AND Delta above the placebo CI
    df["memorisation_evidence"] = False
    for i in df.index[tsfm_rows & df["reject_holm"].astype(bool)]:
        r = df.loc[i]
        pl = df[(df["role"] == "placebo") & (df["windows_of"] == r["windows_of"]) & (df["target"] == r["target"]) & (df["horizon"] == r["horizon"])]
        df.loc[i, "memorisation_evidence"] = bool(len(pl)) and bool((r["delta"] > pl["ci_hi"]).all())
    return df


def economic_table(L_rv: pd.DataFrame, daily: dict, cfg: RunConfig, periods: list[str]) -> pd.DataFrame:
    ec = cfg.economic
    if not ec.enabled or ec.asset not in daily:
        return pd.DataFrame()
    rows = []
    r = daily[ec.asset]["r"].dropna()
    for period in periods:
        S = L_rv[_period_mask(L_rv, period) & (L_rv["ticker"] == ec.asset) & (L_rv["horizon"] == ec.horizon) & (L_rv["window"] == "expanding")]
        if S.empty:
            continue
        common = set.intersection(*[set(g["asset_date"]) for _, g in S.groupby("model")])
        S = S[S["asset_date"].isin(common)]
        if S.empty:
            continue
        for m, g in S.groupby("model"):
            summ, _ = backtest(r, g, target_vol=ec.target_vol_annual, max_leverage=ec.max_leverage, cost_bps=ec.cost_bps)
            rows.append({"period": period, "asset": ec.asset, "model": m, **summ})
        rows.append({"period": period, "asset": ec.asset, "model": "buy_and_hold",
                     **buy_and_hold(r, min(common), max(common) + pd.Timedelta(days=10), ec.target_vol_annual)})
    return pd.DataFrame(rows)


def synthetic_table(fc_syn: pd.DataFrame, cfg: RunConfig, kappa: float) -> pd.DataFrame:
    """Synthetic control: every model's loss relative to the oracle (true conditional mean).

    ``ratio_to_oracle`` = mean model loss / mean oracle loss. Its 95% stationary-bootstrap CI
    (``ratio_to_oracle_lo``/``_hi``, Audit-01 fix 3) resamples origins of the per-origin
    cross-sectional mean losses on paired (series, origin) rows, block length as in section 7.
    The oracle is optimal only in expectation, so a ratio below 1 whose CI covers 1 is sampling
    noise (``ratio_ci_covers_1``); the report words it that way.
    """
    if fc_syn is None or fc_syn.empty:
        return pd.DataFrame()
    S = fc_syn[fc_syn["y_true"].notna()].copy()
    S["mse"] = squared_error(S["y_true"], S["y_pred"])
    S["qlike"] = np.where(S["target"] == "rv", qlike(S["y_true"], S["y_pred"]), np.nan)
    S["qlike_latent"] = np.where(S["target"] == "rv", qlike(kappa * S["y_latent"], S["y_pred"]), np.nan)
    rows = []
    for (kind, h), G in S.groupby(["target", "horizon"]):
        loss = PRIMARY_LOSS[kind]
        oracle = G[G["model"] == "oracle"].set_index(["ticker", "origin"])
        for m, M in G.groupby("model"):
            Mi = M.set_index(["ticker", "origin"])
            j = Mi.join(oracle[[loss]].rename(columns={loss: "oracle"}), how="inner")
            d = (j[loss] - j["oracle"]).groupby(level="origin").mean()
            h_eff = overlap_order(h, cfg.evaluation.stride) + 1
            r = dm_test(d.to_numpy(), h_eff=h_eff) if m != "oracle" else None
            row = {"target": kind, "horizon": h, "model": m, "loss": loss, "n": len(M),
                   "mean_loss": M[loss].mean(), "ratio_to_oracle": M[loss].mean() / oracle[loss].mean(),
                   "dm_vs_oracle_stat": r.stat if r else np.nan, "dm_vs_oracle_p": r.pvalue if r else np.nan}
            if kind == "rv":
                row["qlike_latent"] = M["qlike_latent"].mean()
                row["ratio_to_oracle_latent"] = M["qlike_latent"].mean() / oracle["qlike_latent"].mean()
            lo = hi = np.nan
            if m != "oracle":
                per = j[[loss, "oracle"]].groupby(level="origin").mean().dropna()
                rng = np.random.default_rng(derive_seed(cfg.seed, "synthetic_ratio", kind, h, m))
                _, lo, hi = ratio_ci(per[loss].to_numpy(), per["oracle"].to_numpy(), cfg.stats.n_bootstrap,
                                     block_length(len(per), h_eff), rng)
            row["ratio_to_oracle_lo"], row["ratio_to_oracle_hi"] = lo, hi
            row["ratio_ci_covers_1"] = bool(np.isfinite(lo) and lo <= 1.0 <= hi)
            rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ driver
def evaluate(
    fc: pd.DataFrame,
    daily: dict[str, pd.DataFrame],
    cfg: RunConfig,
    status: dict,
    fc_syn: pd.DataFrame | None = None,
    kappa: float = 1.0,
    *,
    fc_primary: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    """``fc``: main-pass forecasts (stride 5); ``fc_primary``: the stride-1 primary pass
    (amendment A4). Only ``dm_primary`` and the clean side of ``contamination`` read
    ``fc_primary``; every other table is computed from ``fc`` exactly as before A4."""
    scales = pretest_scales(daily, cfg.targets.kinds, cfg.targets.horizons, cfg.evaluation.test_start)
    L = add_losses(fc, cfg, scales)
    L, windows, ccs = add_window_labels(L, cfg, status)
    LP = None
    if fc_primary is not None and len(fc_primary):
        LP, _, _ = add_window_labels(add_losses(fc_primary, cfg, scales), cfg, status)
    periods = ["full", "common_clean"]
    log.info("evaluating %d loss rows; common clean window starts %s", len(L), ccs)
    out: dict[str, pd.DataFrame] = {}
    out["losses"] = L
    out["scales"] = scales
    out["windows"] = pd.DataFrame([w.as_dict() for w in windows.values()]).assign(common_clean_start=str(ccs.date()) if ccs is not None else None)
    out["metrics"] = metrics_table(L, cfg, periods)
    out["losses_primary"] = LP if LP is not None else pd.DataFrame()
    out["dm_primary"] = dm_primary(LP, cfg, status)
    out["dm_all"] = dm_all(L, cfg, periods)
    out["loss_diff_series"] = diff_series(L, cfg)
    out["dm_per_asset"] = dm_per_asset(L, cfg, status)
    out["mcs"] = mcs_table(L, cfg, periods)
    out["probabilistic"] = probabilistic_table(L, cfg, periods)
    out["contamination"] = contamination_table(L, LP, cfg, status)
    out["economic"] = economic_table(L[L["target"] == "rv"], daily, cfg, periods)
    out["synthetic"] = synthetic_table(fc_syn, cfg, kappa)
    missing = fc["y_true"].isna().groupby([fc["target"], fc["horizon"]]).sum().rename("n_missing_target").reset_index()
    out["data_quality"] = missing
    return out
