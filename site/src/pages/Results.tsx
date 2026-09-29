// Results: the stored benchmark tables of every published run, filtered and drawn. The page
// computes no statistics: every number comes from site/public/data/results (exported by
// `make publish-results` from results/<run>/stats), and every card shows its provenance.
import { useEffect, useMemo, useState } from "react";
import { ContaminationChart } from "../components/charts/ContaminationChart";
import { fmt, fmtp, type RunPayload } from "../components/charts/common";
import { DmMatrix } from "../components/charts/DmMatrix";
import { LossDiffChart } from "../components/charts/LossDiffChart";
import { Markdown } from "../components/Markdown";
import { Link } from "react-router-dom";
import { session, store } from "../lib/app";
import { markDone, realResultsPublished } from "../lib/journeyState";

interface IndexEntry {
  run: string; version: string; synthetic: boolean; label: string; payload: string; published_utc: string;
  provenance: { config_hash: string; data_hash: string; git_commit: string; created_utc: string };
}

function Provenance({ e }: { e: IndexEntry }) {
  return (
    <div className="prov" data-testid="provenance">
      run {e.run} · published version {e.version} · config {e.provenance.config_hash?.slice(0, 16)} · data {e.provenance.data_hash?.slice(0, 16)} ·
      commit {e.provenance.git_commit?.slice(0, 12)} · statistics computed {e.provenance.created_utc}
    </div>
  );
}

export default function Results() {
  const [index, setIndex] = useState<IndexEntry[] | null>(null);
  const [runName, setRunName] = useState<string>("");
  const [payload, setPayload] = useState<RunPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [f, setF] = useState({ period: "full", window: "expanding", target: "rv", h: 1, asset: "POOLED", model: "all" });

  useEffect(() => {
    fetch("/data/results/index.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`index.json: ${r.status}`))))
      .then((j) => {
        setIndex(j.runs);
        const real = j.runs.find((r: IndexEntry) => !r.synthetic);
        setRunName((real ?? j.runs.find((r: IndexEntry) => r.run === "default_fixtures") ?? j.runs[0])?.run ?? "");
      })
      .catch((e) => setError(String(e)));
  }, []);
  const entry = index?.find((e) => e.run === runName);
  // Phase 6, "Open the Results page of your real run": counts only once a real run is published
  useEffect(() => {
    if (realResultsPublished() && !store.get("journey_state", "site:results"))
      markDone(store, "site:results", "site", "opened the Results page with real results", session.id);
  }, []);
  useEffect(() => {
    if (!entry) return;
    setPayload(null);
    fetch(`/data/results/${entry.payload}`).then((r) => r.json()).then(setPayload).catch((e) => setError(String(e)));
  }, [entry]);

  const assets = useMemo(() => (payload ? [...new Set(payload.series.keys.map((k) => k.ticker))].filter((t) => t !== "POOLED").sort() : []), [payload]);
  const windows = useMemo(() => (payload ? [...new Set(payload.dm.map((d) => d.window))] : ["expanding"]), [payload]);
  const models = useMemo(() => (payload ? [...new Set(payload.series.keys.filter((k) => k.target === f.target).map((k) => k.model))].sort() : []), [payload, f.target]);

  if (error) return <p className="verdict-bad">Could not load results: {error}</p>;
  if (!index) return <p className="muted">Loading results…</p>;
  const set = (p: Partial<typeof f>) => setF((o) => ({ ...o, ...p }));
  const unavailable = payload ? Object.entries(payload.status).filter(([, s]) => s.status !== "AVAILABLE") : [];
  const primary = payload ? payload.primary.filter((p) => p.target === f.target && p.horizon === f.h) : [];

  return (
    <>
      <h1>Results</h1>
      <p className="sub">Every number here is read from the stored result tables of the study, exported with <code>make publish-results</code>. This page computes no statistics.</p>
      {entry?.synthetic && (
        <div className="banner synthetic" data-testid="synthetic-banner">
          {entry.label}. These are the committed synthetic fixtures: they show the pipeline works, not how the models do on markets.
          {!realResultsPublished() && (
            <> The real version unlocks when you <Link to="/tasks/run-study">run the study on your laptop (Phase 2)</Link> and{" "}
              <Link to="/tasks/publish">publish its results (Phase 5)</Link>.</>
          )}
        </div>
      )}
      <div className="filters" role="group" aria-label="Filters">
        <label className="field">Run
          <select value={runName} onChange={(e) => setRunName(e.target.value)} data-testid="f-run">
            {index.map((r) => <option key={r.run} value={r.run}>{r.run}{r.synthetic ? " (synthetic)" : ""}</option>)}
          </select>
        </label>
        <label className="field">Period
          <select value={f.period} onChange={(e) => set({ period: e.target.value })}>
            <option value="full">full test period</option><option value="common_clean">common clean window</option>
          </select>
        </label>
        <label className="field">Window
          <select value={f.window} onChange={(e) => set({ window: e.target.value })}>{windows.map((w) => <option key={w}>{w}</option>)}</select>
        </label>
        <label className="field">Target
          <select value={f.target} onChange={(e) => set({ target: e.target.value, model: "all" })} data-testid="f-target">
            <option value="returns">returns</option><option value="rv">realised volatility</option><option value="volume">log volume</option>
          </select>
        </label>
        <label className="field">Horizon
          <select value={f.h} onChange={(e) => set({ h: Number(e.target.value) })}>{[1, 5, 20].map((h) => <option key={h} value={h}>{h}</option>)}</select>
        </label>
        <label className="field">Asset
          <select value={f.asset} onChange={(e) => set({ asset: e.target.value })}>
            <option value="POOLED">all assets (pooled)</option>{assets.map((a) => <option key={a}>{a}</option>)}
          </select>
        </label>
        <label className="field">Model (time chart)
          <select value={f.model} onChange={(e) => set({ model: e.target.value })}>
            <option value="all">all models</option>{models.map((m) => <option key={m}>{m}</option>)}
          </select>
        </label>
      </div>
      {!payload || !entry ? <p className="muted">Loading run…</p> : (
        <>
          {unavailable.length > 0 && (
            <div className="banner warn">
              <strong>UNAVAILABLE models</strong> (no numbers exist for them in this run):
              <ul>{unavailable.map(([m, s]) => <li key={m}>{m}: {s.reason}</li>)}</ul>
            </div>
          )}
          <section className="card" data-testid="primary-card">
            <h2>Pre-registered primary tests: {f.target}, h = {f.h}</h2>
            <p className="sub">TSFM vs the reference baseline on stride-1 origins in each model's clean window (amendment A4); Kiefer–Vogelsang fixed-b test; Holm over all 27.</p>
            <div className="tablewrap">
              <table>
                <thead><tr><th>model</th><th>reference</th><th>status</th><th>rel. loss [95% CI]</th><th>t (KV)</th><th>p</th><th>Holm p</th><th>T</th><th>flags</th></tr></thead>
                <tbody>
                  {primary.map((p) => (
                    <tr key={p.model}>
                      <td>{p.model}</td><td>{p.reference}</td><td>{p.status}</td>
                      <td>{p.rel_loss === undefined || p.rel_loss === null ? "–" : `${fmt(p.rel_loss)} [${fmt(p.rel_loss_lo)}, ${fmt(p.rel_loss_hi)}]`}</td>
                      <td>{fmt(p.dm_stat, 2)}</td><td>{fmtp(p.p_value)}</td><td>{fmtp(p.p_holm)}</td><td>{p.T ?? "–"}</td>
                      <td>{p.status === "AVAILABLE" ? (p.flag ?? "") : "see UNAVAILABLE list"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Provenance e={entry} />
          </section>
          <section className="card">
            <h2>Loss differential over time: model − {payload.series.keys.find((k) => k.target === f.target)?.reference ?? "reference"} (falling = model better)</h2>
            <p className="sub">{f.asset === "POOLED" ? "Pooled across assets, normalised losses, full test period." : `Asset ${f.asset}, raw primary loss, full test period.`}</p>
            <LossDiffChart run={payload} target={f.target} h={f.h} window={f.window} asset={f.asset} model={f.model} />
            <Provenance e={entry} />
          </section>
          <section className="card">
            <h2>Diebold–Mariano / MCS matrix: loss relative to the reference</h2>
            <p className="sub">{f.asset === "POOLED" ? `Pooled · ${f.period} · ${f.window} window.` : `Asset ${f.asset} · common clean window · expanding.`}</p>
            <DmMatrix run={payload} period={f.period} window={f.window} asset={f.asset} />
            <Provenance e={entry} />
          </section>
          <div className="grid2">
            <section className="card">
              <h2>Contamination: Δ = ln R_clean − ln R_seen ({f.target}, h = {f.h})</h2>
              <p className="sub">Δ &gt; 0 would be consistent with memorisation. Placebo rows are baseline pairs, which cannot memorise.</p>
              <ContaminationChart run={payload} target={f.target} h={f.h} />
              <div className="tablewrap">
                <table>
                  <thead><tr><th>model</th><th>release</th><th>effective release</th><th>clean from</th></tr></thead>
                  <tbody>{payload.windows.map((w) => <tr key={w.model}><td>{w.model}</td><td>{w.release_date}</td><td>{w.effective_release}</td><td>{w.clean_start}</td></tr>)}</tbody>
                </table>
              </div>
              <Provenance e={entry} />
            </section>
            <section className="card" data-testid="limitations">
              <h2>Limitations</h2>
              <Markdown text={payload.limitations_md} />
              <Provenance e={entry} />
            </section>
          </div>
        </>
      )}
    </>
  );
}
