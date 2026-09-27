"""Static, self-contained results dashboard: ``reports/dashboard/index.html``.

Python packs the *stored* tables of every available run into one JSON blob embedded in the
page; a small vanilla-JavaScript renderer draws SVG charts. The page makes no network
requests, loads no external scripts or fonts, and computes no statistics: it only filters
and plots numbers that already exist in ``results/<run>/stats/*.parquet`` (cumulative loss
differentials included, precomputed by the evaluation stage).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from tsfm_rc.provenance import read_parquet_provenance

RUN_ORDER = ["default", "default_fixtures", "smoke", "smoke_real"]


def _num(x, digits: int = 6):
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return float(f"{f:.{digits}g}")


def _records(df: pd.DataFrame, cols: list[str]) -> list[dict]:
    out = []
    if df is None or df.empty:
        return out
    cols = [c for c in cols if c in df.columns]
    for row in df[cols].itertuples(index=False):
        rec = {}
        for c, v in zip(cols, row, strict=True):
            if isinstance(v, (bool, np.bool_)):
                rec[c] = bool(v)
            elif isinstance(v, (int, np.integer)):
                rec[c] = int(v)
            elif isinstance(v, (float, np.floating)):
                rec[c] = _num(v)
            elif isinstance(v, pd.Timestamp):
                rec[c] = None if pd.isna(v) else v.strftime("%Y-%m-%d")
            else:
                rec[c] = None if v is None or (isinstance(v, float) and math.isnan(v)) else str(v)
        out.append(rec)
    return out


def _series_payload(S: pd.DataFrame) -> dict:
    """Columnar, dictionary-encoded series: dates are day offsets from 1970-01-01."""
    if S is None or S.empty:
        return {"keys": [], "data": []}
    keys, data = [], []
    for k, g in S.groupby(["target", "horizon", "window", "model", "reference", "ticker"], sort=True):
        g = g.sort_values("origin")
        days = ((pd.to_datetime(g["origin"]) - pd.Timestamp("1970-01-01")).dt.days).astype(int).tolist()
        keys.append({"target": k[0], "horizon": int(k[1]), "window": k[2], "model": k[3], "reference": k[4], "ticker": k[5]})
        data.append({"d": days, "y": [_num(v, 5) for v in g["cum_diff"]]})
    return {"keys": keys, "data": data}


def run_payload(run_dir: Path) -> dict | None:
    stats = run_dir / "stats"
    if not (stats / "dm_all.parquet").exists():
        return None

    def rd(name):
        p = stats / f"{name}.parquet"
        return pd.read_parquet(p) if p.exists() else pd.DataFrame()

    prov = read_parquet_provenance(stats / "dm_all.parquet")
    status = json.loads((run_dir / "model_status.json").read_text()) if (run_dir / "model_status.json").exists() else {}
    dm_cols = ["period", "window", "target", "horizon", "model", "reference", "loss", "rel_loss", "rel_loss_lo",
               "rel_loss_hi", "dm_stat", "p_value", "p_holm", "reject_holm", "mean_diff", "T", "flag"]
    return {
        "run": run_dir.name,
        "source": prov.get("data_source", "?"),
        "config_hash": prov.get("config_hash", "?"),
        "data_hash": prov.get("data_hash", "?"),
        "git": prov.get("git", {}).get("commit", "?"),
        "created": prov.get("created_utc", "?"),
        "status": {m: {"status": s.get("status"), "reason": (s.get("reason") or "")[:240], "release": s.get("release_date")}
                   for m, s in status.items()},
        "primary": _records(rd("dm_primary"), ["model", "target", "horizon", "reference", "status", "rel_loss", "rel_loss_lo",
                                               "rel_loss_hi", "dm_stat", "p_value", "p_holm", "reject_holm", "mean_diff", "T", "flag"]),
        "dm": _records(rd("dm_all"), dm_cols),
        "dm_asset": _records(rd("dm_per_asset"), ["period", "target", "horizon", "model", "reference", "ticker", "loss",
                                                  "rel_loss", "dm_stat", "p_value", "p_holm", "reject_holm", "mean_diff", "T", "flag"]),
        "mcs": _records(rd("mcs"), ["period", "target", "horizon", "ticker", "model", "mcs_pvalue", "in_mcs", "mean_loss", "T"]),
        "contamination": _records(rd("contamination"), ["windows_of", "model", "role", "target", "horizon", "status", "delta",
                                                        "ci_lo", "ci_hi", "p_one_sided", "p_holm", "T_seen", "T_clean"]),
        "windows": _records(rd("windows"), ["model", "release_date", "weights_date", "effective_release", "clean_start", "common_clean_start"]),
        "series": _series_payload(rd("loss_diff_series")),
    }


def build_dashboard(results_root: Path, out_path: Path) -> Path:
    runs = []
    for name in RUN_ORDER + sorted(p.name for p in results_root.iterdir() if p.is_dir() and p.name not in RUN_ORDER):
        d = results_root / name
        if d.is_dir():
            pl = run_payload(d)
            if pl is not None:
                runs.append(pl)
    payload = json.dumps({"runs": runs}, separators=(",", ":"), sort_keys=True)
    payload = payload.replace("</", "<\\/")  # never close the <script> element early
    html = TEMPLATE.replace("__DATA__", payload)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TSFM Reality Check dashboard</title>
<style>
:root {
  color-scheme: light;
  --surface: #fcfcfb; --page: #f9f9f7; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10);
  --s1: #2a78d6; --s2: #eb6834; --s3: #1baf7a; --s4: #eda100; --s5: #e87ba4; --s6: #008300; --s7: #4a3aa7; --s8: #e34948;
  --mid: #f0efec; --b1: #cde2fb; --b2: #86b6ef; --b3: #2a78d6; --r1: #f9d2d1; --r2: #ef9291; --r3: #e34948;
  --warn-bg: #fff4dc; --warn-ink: #5c4300;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --surface: #1a1a19; --page: #0d0d0d; --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
    --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500; --s5: #d55181; --s6: #008300; --s7: #9085e9; --s8: #e66767;
    --mid: #383835; --b1: #184f95; --b2: #256abf; --b3: #3987e5; --r1: #6b2525; --r2: #a33c3c; --r3: #e66767;
    --warn-bg: #3a2e10; --warn-ink: #fbe3a6;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface: #1a1a19; --page: #0d0d0d; --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
  --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500; --s5: #d55181; --s6: #008300; --s7: #9085e9; --s8: #e66767;
  --mid: #383835; --b1: #184f95; --b2: #256abf; --b3: #3987e5; --r1: #6b2525; --r2: #a33c3c; --r3: #e66767;
  --warn-bg: #3a2e10; --warn-ink: #fbe3a6;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink); font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
header, main { max-width: 1180px; margin: 0 auto; padding: 16px; }
h1 { font-size: 20px; margin: 8px 0 4px; }
h2 { font-size: 15px; margin: 0 0 8px; }
.sub { color: var(--ink-2); font-size: 13px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px; margin: 14px 0; }
.banner { background: var(--warn-bg); color: var(--warn-ink); border-radius: 10px; padding: 10px 14px; margin: 10px 0; font-size: 13px; }
.banner ul { margin: 4px 0 0 18px; padding: 0; }
.filters { display: flex; flex-wrap: wrap; gap: 10px; align-items: end; position: sticky; top: 0; z-index: 5;
  background: var(--page); padding: 10px 0; border-bottom: 1px solid var(--border); }
.filters label { display: flex; flex-direction: column; font-size: 11px; color: var(--ink-2); gap: 2px; }
select, button { font: inherit; font-size: 13px; color: var(--ink); background: var(--surface); border: 1px solid var(--axis);
  border-radius: 6px; padding: 4px 8px; }
button { cursor: pointer; }
.chart { width: 100%; overflow: hidden; }
svg text { fill: var(--ink-2); font-size: 11px; }
svg .axis line, svg .axis path { stroke: var(--axis); }
svg .grid line { stroke: var(--grid); }
.legend { display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; color: var(--ink-2); margin: 6px 0; }
.legend span.key { display: inline-block; width: 14px; height: 2px; margin-right: 5px; vertical-align: middle; }
.tooltip { position: fixed; pointer-events: none; background: var(--surface); color: var(--ink); border: 1px solid var(--border);
  border-radius: 8px; padding: 8px 10px; font-size: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.15); display: none; z-index: 20; max-width: 360px; }
.tooltip .row { display: flex; gap: 8px; align-items: center; }
.tooltip .val { font-weight: 600; }
.tooltip .lab { color: var(--ink-2); }
.tooltip .key { width: 12px; height: 2px; display: inline-block; }
table { border-collapse: collapse; width: 100%; font-size: 12px; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 4px 6px; border-bottom: 1px solid var(--grid); }
th { color: var(--ink-2); font-weight: 600; }
.matrix td.cell { text-align: center; cursor: default; min-width: 64px; border: 2px solid var(--surface); border-radius: 4px; }
.matrix td.cell:focus { outline: 2px solid var(--ink); }
.c-b3 { background: var(--b3); color: #fff; } .c-b2 { background: var(--b2); color: var(--ink); } .c-b1 { background: var(--b1); color: var(--ink); }
.c-0 { background: var(--mid); color: var(--ink); } .c-r1 { background: var(--r1); color: var(--ink); } .c-r2 { background: var(--r2); color: var(--ink); }
.c-r3 { background: var(--r3); color: #fff; } .c-na { background: transparent; color: var(--muted); }
.scale { display: flex; gap: 2px; align-items: center; font-size: 11px; color: var(--ink-2); margin-top: 8px; flex-wrap: wrap; }
.scale span.sw { width: 26px; height: 12px; border-radius: 3px; display: inline-block; }
.note { color: var(--muted); font-size: 12px; }
.grid2 { display: grid; grid-template-columns: 1fr; gap: 14px; }
@media (min-width: 900px) { .grid2 { grid-template-columns: 1fr 1fr; } }
.tablewrap { overflow-x: auto; max-height: 420px; overflow-y: auto; }
</style>
</head>
<body>
<header>
  <h1>TSFM Reality Check: results dashboard</h1>
  <div class="sub">Every number on this page is read from stored result tables (<code>results/&lt;run&gt;/stats/*.parquet</code>). The page computes no statistics.</div>
  <div id="banner"></div>
  <div class="filters" role="group" aria-label="Filters">
    <label>Run <select id="f-run"></select></label>
    <label>Period <select id="f-period"><option value="full">full test period</option><option value="common_clean">common clean window</option></select></label>
    <label>Window <select id="f-window"></select></label>
    <label>Target <select id="f-target"><option value="returns">returns</option><option value="rv">realised vol</option><option value="volume">log volume</option></select></label>
    <label>Horizon <select id="f-h"><option>1</option><option>5</option><option>20</option></select></label>
    <label>Asset <select id="f-asset"></select></label>
    <label>Model (time chart) <select id="f-model"></select></label>
    <button id="theme" type="button" aria-label="Toggle light or dark theme">Theme</button>
  </div>
</header>
<main>
  <section class="card"><h2>Pre-registered primary tests (TSFM vs reference, clean window)</h2>
    <div class="tablewrap"><table id="primary"></table></div></section>
  <section class="card"><h2 id="ts-title">Cumulative loss differential over time</h2>
    <div class="note" id="ts-note"></div><div class="legend" id="ts-legend"></div><div class="chart" id="ts"></div></section>
  <section class="card"><h2>Diebold–Mariano / MCS matrix: loss relative to the reference</h2>
    <div class="note" id="mx-note"></div><div class="tablewrap"><table class="matrix" id="matrix"></table></div>
    <div class="scale" id="mx-scale"></div></section>
  <div class="grid2">
    <section class="card"><h2>Contamination: Δ = ln R_clean − ln R_seen</h2>
      <div class="note">Δ &gt; 0 would be consistent with memorisation. Placebo rows are baseline pairs, which cannot memorise.</div>
      <div class="legend" id="ct-legend"></div><div class="chart" id="contam"></div>
      <div class="tablewrap"><table id="windows"></table></div></section>
    <section class="card"><h2>Table view of the matrix selection</h2><div class="tablewrap"><table id="tableview"></table></div></section>
  </div>
  <div class="note" id="prov"></div>
</main>
<div class="tooltip" id="tip" role="status" aria-live="polite"></div>
<script type="application/json" id="tsfm-data">__DATA__</script>
<script>
"use strict";
const DATA = JSON.parse(document.getElementById("tsfm-data").textContent);
const SLOT = { chronos_bolt_tiny: 1, timesfm_2p5_200m: 2, moirai_1p1_small: 3, lgbm: 4, ar_bic: 5, garch: 5,
               hist_mean: 6, ewma: 6, seasonal_naive: 6, gjr_garch: 7, oracle: 8 };
const TSFM = new Set(["chronos_bolt_tiny", "timesfm_2p5_200m", "moirai_1p1_small"]);
const $ = (id) => document.getElementById(id);
const SVGNS = "http://www.w3.org/2000/svg";
const el = (tag, attrs = {}, text) => { const e = document.createElementNS(SVGNS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (text !== undefined) e.textContent = text; return e; };
const h = (tag, text, cls) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; };
const colorOf = (m) => `var(--s${SLOT[m] || 8})`;
const fmt = (x, d = 3) => (x === null || x === undefined || !isFinite(x)) ? "–" : Number(x).toFixed(d);
const fmtp = (p) => (p === null || p === undefined || !isFinite(p)) ? "–" : (p < 0.001 ? "<0.001" : Number(p).toFixed(3));
const dayToDate = (d) => new Date(d * 86400000).toISOString().slice(0, 10);
const tip = $("tip");
function showTip(evt, rows) {
  tip.replaceChildren();
  for (const r of rows) {
    const row = h("div", undefined, "row");
    if (r.color) { const k = h("span", undefined, "key"); k.style.background = r.color; row.appendChild(k); }
    row.appendChild(h("span", r.value, "val")); row.appendChild(h("span", r.label, "lab"));
    tip.appendChild(row);
  }
  tip.style.display = "block";
  const x = (evt.clientX ?? evt.target.getBoundingClientRect().right) + 14, y = (evt.clientY ?? evt.target.getBoundingClientRect().top) + 10;
  tip.style.left = Math.min(x, window.innerWidth - tip.offsetWidth - 8) + "px";
  tip.style.top = Math.min(y, window.innerHeight - tip.offsetHeight - 8) + "px";
}
function hideTip() { tip.style.display = "none"; }

const state = { run: 0 };
const run = () => DATA.runs[state.run];
function option(sel, value, label) { const o = document.createElement("option"); o.value = value; o.textContent = label ?? value; sel.appendChild(o); }

function setupRun() {
  const r = run();
  const windows = [...new Set(r.dm.map((d) => d.window))];
  const fw = $("f-window"); fw.replaceChildren(); windows.forEach((w) => option(fw, w));
  const assets = [...new Set(r.series.keys.map((k) => k.ticker))].filter((t) => t !== "POOLED").sort();
  const fa = $("f-asset"); fa.replaceChildren(); option(fa, "POOLED", "all assets (pooled)"); assets.forEach((a) => option(fa, a));
  // banner
  const b = $("banner"); b.replaceChildren();
  const box = h("div", undefined, "banner");
  box.appendChild(h("strong", r.source === "fixture" ? "Synthetic fixture data: not market data. " : `Data source: ${r.source}. `));
  const un = Object.entries(r.status).filter(([, s]) => s.status !== "AVAILABLE");
  if (un.length) {
    box.appendChild(h("span", "UNAVAILABLE models (no numbers shown for them):"));
    const ul = h("ul"); un.forEach(([m, s]) => ul.appendChild(h("li", `${m}: ${s.reason}`))); box.appendChild(ul);
  }
  b.appendChild(box);
  $("prov").textContent = `Run ${r.run} · config ${r.config_hash.slice(0, 16)} · data ${r.data_hash.slice(0, 16)} · git ${r.git.slice(0, 12)} · statistics computed ${r.created} (UTC)`;
}

function current() {
  return { period: $("f-period").value, window: $("f-window").value, target: $("f-target").value,
           h: Number($("f-h").value), asset: $("f-asset").value, model: $("f-model").value };
}

function renderPrimary(f) {
  const t = $("primary"); t.replaceChildren();
  const head = h("tr"); ["model", "target", "h", "reference", "status", "rel. loss [95% CI]", "DM", "p", "Holm p", "T", "flags"].forEach((c) => head.appendChild(h("th", c)));
  t.appendChild(head);
  run().primary.filter((p) => p.target === f.target && p.horizon === f.h).forEach((p) => {
    const tr = h("tr");
    const ci = (p.rel_loss === null || p.rel_loss === undefined) ? "–" : `${fmt(p.rel_loss)} [${fmt(p.rel_loss_lo)}, ${fmt(p.rel_loss_hi)}]`;
    const flag = p.status === "AVAILABLE" ? (p.flag ?? "") : "see UNAVAILABLE list above";
    [p.model, p.target, p.horizon, p.reference, p.status, ci, fmt(p.dm_stat, 2), fmtp(p.p_value), fmtp(p.p_holm), p.T ?? "–", flag]
      .forEach((v) => tr.appendChild(h("td", String(v))));
    t.appendChild(tr);
  });
}

function renderSeries(f) {
  const r = run(); const box = $("ts"); box.replaceChildren(); const leg = $("ts-legend"); leg.replaceChildren();
  const want = r.series.keys.map((k, i) => [k, i]).filter(([k]) => k.target === f.target && k.horizon === f.h && k.window === f.window
    && k.ticker === f.asset && (f.model === "all" || k.model === f.model));
  const ref = want.length ? want[0][0].reference : "";
  $("ts-title").textContent = `Cumulative loss differential over time: model − ${ref || "reference"} (falling line = model better)`;
  $("ts-note").textContent = f.asset === "POOLED" ? "Pooled across assets, normalised losses (period filter does not apply: full test period)." :
    (f.window !== "expanding" ? "Per-asset series are stored for the expanding window only." : `Asset ${f.asset}, raw primary loss, full test period.`);
  if (!want.length) { box.appendChild(h("div", "No stored series for this selection.", "note")); return; }
  const W = Math.max(320, box.clientWidth || 900), H = 300, m = { l: 56, r: 16, t: 10, b: 28 };
  const all = want.map(([k, i]) => ({ k, d: r.series.data[i].d, y: r.series.data[i].y }));
  const xs = all.flatMap((s) => s.d), ys = all.flatMap((s) => s.y).concat([0]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const X = (d) => m.l + (d - x0) / Math.max(1, x1 - x0) * (W - m.l - m.r);
  const Y = (v) => m.t + (1 - (v - y0) / Math.max(1e-12, y1 - y0)) * (H - m.t - m.b);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: "100%", role: "img", "aria-label": "Cumulative loss differential chart" });
  const g = el("g", { class: "grid" });
  for (let i = 0; i <= 4; i++) { const v = y0 + (y1 - y0) * i / 4; g.appendChild(el("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v) }));
    svg.appendChild(el("text", { x: m.l - 6, y: Y(v) + 4, "text-anchor": "end" }, fmt(v, Math.abs(y1 - y0) < 1 ? 3 : 1))); }
  svg.appendChild(g);
  for (let i = 0; i <= 5; i++) { const d = x0 + (x1 - x0) * i / 5;
    svg.appendChild(el("text", { x: X(d), y: H - 8, "text-anchor": i === 0 ? "start" : i === 5 ? "end" : "middle" }, dayToDate(Math.round(d)).slice(0, 7))); }
  svg.appendChild(el("line", { x1: m.l, x2: W - m.r, y1: Y(0), y2: Y(0), stroke: "var(--axis)", "stroke-width": 1 }));
  for (const s of all) {
    const p = s.d.map((d, j) => `${j ? "L" : "M"}${X(d).toFixed(1)},${Y(s.y[j]).toFixed(1)}`).join("");
    svg.appendChild(el("path", { d: p, fill: "none", stroke: colorOf(s.k.model), "stroke-width": 2, "stroke-linejoin": "round" }));
    const li = h("span"); const key = h("span", undefined, "key"); key.style.background = colorOf(s.k.model); li.appendChild(key); li.appendChild(document.createTextNode(s.k.model)); leg.appendChild(li);
  }
  const cross = el("line", { y1: m.t, y2: H - m.b, stroke: "var(--muted)", "stroke-width": 1, visibility: "hidden" });
  svg.appendChild(cross);
  const hit = el("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: "transparent", tabindex: 0 });
  const onMove = (evt) => {
    const rect = svg.getBoundingClientRect(); const px = (evt.clientX - rect.left) * W / rect.width;
    const d = x0 + (px - m.l) / (W - m.l - m.r) * (x1 - x0);
    const rows = [];
    let nearest = null;
    for (const s of all) { let j = 0, bd = Infinity; s.d.forEach((v, k) => { const dd = Math.abs(v - d); if (dd < bd) { bd = dd; j = k; } });
      if (nearest === null || Math.abs(s.d[j] - d) < Math.abs(nearest - d)) nearest = s.d[j];
      rows.push({ color: colorOf(s.k.model), value: fmt(s.y[j]), label: s.k.model }); }
    cross.setAttribute("x1", X(nearest)); cross.setAttribute("x2", X(nearest)); cross.setAttribute("visibility", "visible");
    showTip(evt, [{ value: dayToDate(nearest), label: "origin" }, ...rows]);
  };
  hit.addEventListener("pointermove", onMove);
  hit.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); hideTip(); });
  svg.appendChild(hit);
  box.appendChild(svg);
}

function binClass(rel) {
  if (rel === null || rel === undefined || !isFinite(rel) || rel <= 0) return "c-na";
  const z = Math.log(rel);
  if (z <= -0.15) return "c-b3"; if (z <= -0.05) return "c-b2"; if (z <= -0.02) return "c-b1";
  if (z < 0.02) return "c-0"; if (z < 0.05) return "c-r1"; if (z < 0.15) return "c-r2"; return "c-r3";
}

function renderMatrix(f) {
  const r = run(); const t = $("matrix"); t.replaceChildren(); const tv = $("tableview"); tv.replaceChildren();
  const pooled = f.asset === "POOLED";
  let rows;
  if (pooled) rows = r.dm.filter((d) => d.period === f.period && d.window === f.window);
  else rows = (f.period === "common_clean" && f.window === "expanding") ? r.dm_asset.filter((d) => d.period === "common_clean" && d.ticker === f.asset) : [];
  $("mx-note").textContent = pooled ? `Pooled across assets · ${f.period} · ${f.window} window. ★ = Holm-significant; ● = in the Model Confidence Set.` :
    (rows.length ? `Asset ${f.asset} · common clean window · expanding. ★ = Holm-significant within the per-asset family; ● = in this asset's MCS.` :
      "Per-asset tests are stored for the common clean window with the expanding window only: switch Period and Window.");
  const mcsRows = r.mcs.filter((c) => c.period === f.period && c.ticker === (pooled ? "POOLED" : f.asset));
  const cols = []; ["returns", "rv", "volume"].forEach((tg) => [1, 5, 20].forEach((hh) => cols.push([tg, hh])));
  const models = [...new Set(rows.map((d) => d.model))].sort();
  const head = h("tr"); head.appendChild(h("th", "model")); cols.forEach(([tg, hh]) => head.appendChild(h("th", `${tg} h=${hh}`))); t.appendChild(head);
  for (const mo of models) {
    const tr = h("tr"); tr.appendChild(h("td", mo));
    for (const [tg, hh] of cols) {
      const d = rows.find((x) => x.model === mo && x.target === tg && x.horizon === hh);
      const mc = mcsRows.find((x) => x.model === mo && x.target === tg && x.horizon === hh);
      const td = h("td", undefined, "cell " + binClass(d ? d.rel_loss : null));
      if (d) {
        td.textContent = `${fmt(d.rel_loss, 2)}${d.reject_holm ? " ★" : ""}${mc && mc.in_mcs ? " ●" : ""}`;
        td.tabIndex = 0;
        const rowsTip = [
          { value: `${mo}`, label: `vs ${d.reference} · ${tg} h=${hh}` },
          { value: d.rel_loss_lo !== undefined && d.rel_loss_lo !== null ? `${fmt(d.rel_loss)} [${fmt(d.rel_loss_lo)}, ${fmt(d.rel_loss_hi)}]` : fmt(d.rel_loss), label: "relative loss [95% CI]" },
          { value: fmt(d.dm_stat, 2), label: "DM statistic" }, { value: fmtp(d.p_value), label: "p" }, { value: fmtp(d.p_holm), label: "Holm p" },
          { value: mc ? fmtp(mc.mcs_pvalue) : "–", label: "MCS p" }, { value: String(d.T ?? "–"), label: "origins (T)" },
        ];
        if (d.flag) rowsTip.push({ value: d.flag, label: "flags" });
        td.addEventListener("pointermove", (e) => showTip(e, rowsTip));
        td.addEventListener("focus", (e) => showTip(e, rowsTip));
        td.addEventListener("pointerleave", hideTip); td.addEventListener("blur", hideTip);
      } else if (mc) { td.textContent = mc.in_mcs ? "ref ●" : "ref"; }
      tr.appendChild(td);
    }
    t.appendChild(tr);
  }
  // table view (accessible, no hover needed)
  const th = h("tr"); ["target", "h", "model", "reference", "rel. loss", "DM", "p", "Holm p", "T"].forEach((c) => th.appendChild(h("th", c))); tv.appendChild(th);
  rows.filter((d) => d.target === f.target).forEach((d) => { const tr = h("tr");
    [d.target, d.horizon, d.model, d.reference, fmt(d.rel_loss), fmt(d.dm_stat, 2), fmtp(d.p_value), fmtp(d.p_holm), d.T ?? "–"].forEach((v) => tr.appendChild(h("td", String(v)))); tv.appendChild(tr); });
  const sc = $("mx-scale"); sc.replaceChildren(); sc.appendChild(h("span", "model better ")); ["c-b3", "c-b2", "c-b1", "c-0", "c-r1", "c-r2", "c-r3"].forEach((c) => sc.appendChild(h("span", undefined, "sw " + c)));
  sc.appendChild(h("span", " model worse · bins at relative loss ≈ 0.86, 0.95, 0.98, 1.02, 1.05, 1.16"));
}

function renderContamination(f) {
  const r = run(); const box = $("contam"); box.replaceChildren(); const leg = $("ct-legend"); leg.replaceChildren();
  const rows = r.contamination.filter((c) => c.target === f.target && c.horizon === f.h && c.delta !== null && c.delta !== undefined);
  const wt = $("windows"); wt.replaceChildren();
  const hr = h("tr"); ["model", "release", "effective release", "clean window starts"].forEach((c) => hr.appendChild(h("th", c))); wt.appendChild(hr);
  r.windows.forEach((w) => { const tr = h("tr"); [w.model, w.release_date, w.effective_release, w.clean_start].forEach((v) => tr.appendChild(h("td", String(v ?? "–")))); wt.appendChild(tr); });
  if (!rows.length) { box.appendChild(h("div", "No contamination statistics for this selection.", "note")); return; }
  [["TSFM", "var(--s2)"], ["placebo (baseline pair)", "var(--s1)"]].forEach(([lab, c]) => { if (rows.some((x) => (x.role === "tsfm") === (lab === "TSFM"))) {
    const li = h("span"); const k = h("span", undefined, "key"); k.style.background = c; li.appendChild(k); li.appendChild(document.createTextNode(lab)); leg.appendChild(li); } });
  const W = Math.max(320, box.clientWidth || 520), rowH = 26, m = { l: Math.min(250, W * 0.5), r: 16, t: 8, b: 24 }, H = m.t + m.b + rowH * rows.length;
  const lo = Math.min(0, ...rows.map((x) => x.ci_lo ?? x.delta)), hi = Math.max(0, ...rows.map((x) => x.ci_hi ?? x.delta));
  const X = (v) => m.l + (v - lo) / Math.max(1e-9, hi - lo) * (W - m.l - m.r);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: "100%", role: "img", "aria-label": "Contamination statistic chart" });
  svg.appendChild(el("line", { x1: X(0), x2: X(0), y1: m.t, y2: H - m.b, stroke: "var(--axis)", "stroke-width": 1 }));
  const dec = Math.max(2, Math.ceil(-Math.log10(Math.max(1e-9, (hi - lo) / 2))) + 1);
  for (let i = 0; i <= 2; i++) { const v = lo + (hi - lo) * i / 2;
    svg.appendChild(el("text", { x: X(v), y: H - 6, "text-anchor": i === 0 ? "start" : i === 2 ? "end" : "middle" }, fmt(v, dec))); }
  rows.forEach((c, i) => {
    const y = m.t + rowH * (i + 0.5); const col = c.role === "tsfm" ? "var(--s2)" : "var(--s1)";
    svg.appendChild(el("text", { x: m.l - 8, y: y + 4, "text-anchor": "end" }, `${c.model} · ${c.windows_of.split("_")[0]} windows`));
    if (c.ci_lo !== null) svg.appendChild(el("line", { x1: X(c.ci_lo), x2: X(c.ci_hi), y1: y, y2: y, stroke: col, "stroke-width": 2, "stroke-linecap": "round" }));
    svg.appendChild(el("circle", { cx: X(c.delta), cy: y, r: 5, fill: col, stroke: "var(--surface)", "stroke-width": 2 }));
    const hit = el("rect", { x: m.l, y: y - rowH / 2, width: W - m.l - m.r, height: rowH, fill: "transparent", tabindex: 0 });
    const tr = [{ value: fmt(c.delta), label: `Δ · ${c.model} (${c.role})` }, { value: `[${fmt(c.ci_lo)}, ${fmt(c.ci_hi)}]`, label: "95% CI" },
      { value: fmtp(c.p_one_sided), label: "p (Δ > 0)" }, { value: c.role === "tsfm" ? fmtp(c.p_holm) : "–", label: "Holm p" },
      { value: `${c.T_seen ?? "–"}/${c.T_clean ?? "–"}`, label: "origins seen/clean" }];
    hit.addEventListener("pointermove", (e) => showTip(e, tr)); hit.addEventListener("focus", (e) => showTip(e, tr));
    hit.addEventListener("pointerleave", hideTip); hit.addEventListener("blur", hideTip);
    svg.appendChild(hit);
  });
  box.appendChild(svg);
}

function updateModelFilter(f) {
  const fm = $("f-model"); const keep = fm.value;
  const models = [...new Set(run().series.keys.filter((k) => k.target === f.target).map((k) => k.model))].sort();
  fm.replaceChildren(); option(fm, "all", "all models"); models.forEach((m) => option(fm, m));
  fm.value = models.includes(keep) ? keep : "all";
}

function render() { let f = current(); updateModelFilter(f); f = current(); renderPrimary(f); renderSeries(f); renderMatrix(f); renderContamination(f); }

(function init() {
  const fr = $("f-run");
  if (!DATA.runs.length) { document.querySelector("main").replaceChildren(h("p", "No stored results found. Run `make smoke` first.")); return; }
  DATA.runs.forEach((r, i) => option(fr, String(i), `${r.run}${r.source === "fixture" ? " (synthetic)" : ""}`));
  fr.addEventListener("change", () => { state.run = Number(fr.value); setupRun(); render(); });
  ["f-period", "f-window", "f-target", "f-h", "f-asset", "f-model"].forEach((id) => $(id).addEventListener("change", render));
  $("theme").addEventListener("click", () => { const d = document.documentElement; const dark = d.getAttribute("data-theme") === "dark" ||
    (!d.getAttribute("data-theme") && matchMedia("(prefers-color-scheme: dark)").matches); d.setAttribute("data-theme", dark ? "light" : "dark"); });
  window.addEventListener("resize", () => render());
  if (location.hash === "#dark" || location.hash === "#light") document.documentElement.setAttribute("data-theme", location.hash.slice(1));
  setupRun(); render();
})();
</script>
</body>
</html>
"""
