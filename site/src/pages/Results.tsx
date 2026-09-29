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
import { PathRail, pathToggleLabel } from "../components/Journey";
import { Loading, Shell } from "../components/Shell";
import { session, store, useStore } from "../lib/app";
import { markDone, realResultsPublished, useJourney } from "../lib/journeyState";

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
  useStore();
  const v = useJourney();
  const [attempt, setAttempt] = useState(0);
  const [index, setIndex] = useState<IndexEntry[] | null>(null);
  const [runName, setRunName] = useState<string>("");
  const [payload, setPayload] = useState<RunPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [f, setF] = useState({ period: "full", window: "expanding", target: "rv", h: 1, asset: "POOLED", model: "all" });

  useEffect(() => {
    setError(null);
    fetch("/data/results/index.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`index.json: ${r.status}`))))
      .then((j) => {
        setIndex(j.runs);
        const real = j.runs.find((r: IndexEntry) => !r.synthetic);
        setRunName((real ?? j.runs.find((r: IndexEntry) => r.run === "default_fixtures") ?? j.runs[0])?.run ?? "");
      })
      .catch((e) => setError(String(e)));
  }, [attempt]);
  const entry = index?.find((e) => e.run === runName);
  // Phase 6, "Open the Results page of your real run": counts only once a real run is published
  useEffect(() => {
    if (realResultsPublished() && !store.get("journey_state", "site:results"))
      markDone(store, "site:results", "site", "opened the Results page with real results", session.id);
  }, []);
  useEffect(() => {
    if (!entry) return;
    setPayload(null);
    fetch(`/data/results/${entry.payload}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${entry.payload}: ${r.status}`))))
      .then(setPayload).catch((e) => setError(String(e)));
  }, [entry, attempt]);

  const assets = useMemo(() => (payload ? [...new Set(payload.series.keys.map((k) => k.ticker))].filter((t) => t !== "POOLED").sort() : []), [payload]);
  const windows = useMemo(() => (payload ? [...new Set(payload.dm.map((d) => d.window))] : ["expanding"]), [payload]);
  const models = useMemo(() => (payload ? [...new Set(payload.series.keys.filter((k) => k.target === f.target).map((k) => k.model))].sort() : []), [payload, f.target]);

  const shell = (body: React.ReactNode) => <Shell rail={<PathRail v={v} />} railToggle={pathToggleLabel(v)}><div className="content wide">{body}</div></Shell>;
  if (error)
    return shell(
      <div className="notice error" role="alert" data-testid="results-error">
        <p><span className="label">The results could not be loaded.</span> {error}. Check your connection and try again; lessons and
          your progress are not affected.</p>
        <button type="button" onClick={() => setAttempt((n) => n + 1)} data-testid="results-retry">Try again</button>
      </div>,
    );
  if (!index) return shell(<><h1>Results</h1><Loading text="Loading results…" /></>);
  const set = (p: Partial<typeof f>) => setF((o) => ({ ...o, ...p }));
  const unavailable = payload ? Object.entries(payload.status).filter(([, s]) => s.status !== "AVAILABLE") : [];
  const primary = payload ? payload.primary.filter((p) => p.target === f.target && p.horizon === f.h) : [];

  return shell(
    <>
      <h1>Results</h1>
      <p className="lede">Every number here is read from the stored result tables of the study, exported with <code>make publish-results</code>. This page computes no statistics.</p>
      {entry?.synthetic && (
        <div className="notice synthetic" data-testid="synthetic-banner">
          <span className="label">{entry.label}.</span> These are the committed synthetic fixtures: they show the pipeline works, not how the models do on markets.
          {!realResultsPublished() && (
            <> The real version appears when you <Link to="/tasks/run-study">run the study on your laptop (Phase 2)</Link> and{" "}
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
      {!payload || !entry ? <Loading text="Loading this run…" /> : (
        <>
          {unavailable.length > 0 && (
            <details className="notice" data-testid="unavailable">
              <summary><span className="label">{unavailable.length} model{unavailable.length === 1 ? " is" : "s are"} UNAVAILABLE in this run</span>{" "}
                (no numbers exist for {unavailable.length === 1 ? "it" : "them"}): {unavailable.map(([m]) => m).join(", ")}. Why</summary>
              <ul>{unavailable.map(([m, s]) => <li key={m}><strong>{m}</strong>: <span className="small-text">{s.reason}</span></li>)}</ul>
            </details>
          )}
          <section className="results-section" data-testid="primary-card" aria-labelledby="primary-title">
            <h2 id="primary-title">Pre-registered primary tests: {f.target}, h = {f.h}</h2>
            <p className="sub">TSFM vs the reference baseline on stride-1 origins in each model's clean window (amendment A4); Kiefer–Vogelsang fixed-b test; Holm over all 27.</p>
            <div className="tablewrap">
              <table className="stack">
                <thead><tr><th scope="col">Model</th><th scope="col">Reference</th><th scope="col">Status</th><th scope="col">Rel. loss [95% CI]</th><th scope="col">t (KV)</th>
                  <th scope="col">p</th><th scope="col">Holm p</th><th scope="col">T</th><th scope="col">Flags</th></tr></thead>
                <tbody>
                  {primary.map((p) => (
                    <tr key={p.model}>
                      <th scope="row">{p.model}</th><td data-label="Reference">{p.reference}</td><td data-label="Status">{p.status}</td>
                      <td data-label="Rel. loss [95% CI]">{p.rel_loss === undefined || p.rel_loss === null ? "–" : `${fmt(p.rel_loss)} [${fmt(p.rel_loss_lo)}, ${fmt(p.rel_loss_hi)}]`}</td>
                      <td data-label="t (KV)">{fmt(p.dm_stat, 2)}</td><td data-label="p">{fmtp(p.p_value)}</td><td data-label="Holm p">{fmtp(p.p_holm)}</td>
                      <td data-label="T">{p.T ?? "–"}</td>
                      <td data-label="Flags">{p.status === "AVAILABLE" ? (p.flag ?? "") : "see UNAVAILABLE list"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Provenance e={entry} />
          </section>
          <section className="results-section" aria-labelledby="lossdiff-title">
            <h2 id="lossdiff-title">Loss differential over time: model − {payload.series.keys.find((k) => k.target === f.target)?.reference ?? "reference"} (falling = model better)</h2>
            <p className="sub">{f.asset === "POOLED" ? "Pooled across assets, normalised losses, full test period." : `Asset ${f.asset}, raw primary loss, full test period.`}</p>
            <LossDiffChart run={payload} target={f.target} h={f.h} window={f.window} asset={f.asset} model={f.model} />
            <Provenance e={entry} />
          </section>
          <section className="results-section" aria-labelledby="dm-title">
            <h2 id="dm-title">Diebold–Mariano / MCS matrix: loss relative to the reference</h2>
            <p className="sub">{f.asset === "POOLED" ? `Pooled · ${f.period} · ${f.window} window.` : `Asset ${f.asset} · common clean window · expanding.`}</p>
            <DmMatrix run={payload} period={f.period} window={f.window} asset={f.asset} />
            <Provenance e={entry} />
          </section>
          <div className="two-col">
            <section className="results-section" aria-labelledby="contam-title">
              <h2 id="contam-title">Contamination: Δ = ln R_clean − ln R_seen ({f.target}, h = {f.h})</h2>
              <p className="sub">Δ &gt; 0 would be consistent with memorisation. Placebo rows are baseline pairs, which cannot memorise.</p>
              <ContaminationChart run={payload} target={f.target} h={f.h} />
              <div className="tablewrap">
                <table className="stack compact">
                  <thead><tr><th scope="col">Model</th><th scope="col">Release</th><th scope="col">Effective release</th><th scope="col">Clean from</th></tr></thead>
                  <tbody>{payload.windows.map((w) => <tr key={w.model}><th scope="row">{w.model}</th><td data-label="Release">{w.release_date}</td>
                    <td data-label="Effective release">{w.effective_release}</td><td data-label="Clean from">{w.clean_start}</td></tr>)}</tbody>
                </table>
              </div>
              <Provenance e={entry} />
            </section>
            <section className="results-section" data-testid="limitations" aria-labelledby="lim-title">
              <h2 id="lim-title">Limitations</h2>
              <Markdown text={payload.limitations_md} className="prose ui" />
              <Provenance e={entry} />
            </section>
          </div>
        </>
      )}
    </>,
  );
}
