import { researchStatus as S } from "../lib/content";
import { TerminalTaskCard } from "../components/TerminalTaskCard";

export function Status() {
  return (
    <>
      <h1>Research status</h1>
      <p className="sub">
        Generated when the site is built, from <code>docs/BUILD-REPORT.md</code>, the amendments in <code>docs/PREREGISTRATION.md</code> and the
        published results{S.generated_from.commit ? <> (commit <code>{S.generated_from.commit.slice(0, 12)}</code>)</> : null}.
      </p>
      <section className="card" data-testid="phases">
        <h2>Research phases</h2>
        {S.phases.map((p) => (
          <div className="phase" key={p.id}>
            <span className={`mark ${p.status}`} aria-label={p.status}>{p.status === "done" ? "✓" : "○"}</span>
            <div><strong>{p.title}</strong><div className="sub">{p.status === "done" ? "Done. " : "Pending. "}{p.detail}</div></div>
          </div>
        ))}
      </section>
      {S.terminal_tasks.map((t) => <TerminalTaskCard key={t.id} task={t} />)}
      <section className="card">
        <h2>Models, per published run</h2>
        {S.runs.map((r) => (
          <div key={r.run} style={{ marginBottom: 12 }}>
            <strong>{r.run}</strong> {r.synthetic && <span className="status-tag locked">{r.label}</span>}
            <div className="prov">version {r.version} · published {r.published_utc} · commit {String(r.provenance.git_commit ?? "?").slice(0, 12)}</div>
            <table>
              <thead><tr><th>model</th><th>status</th><th>documented release</th><th>reason</th></tr></thead>
              <tbody>
                {Object.entries(r.model_status).map(([m, s]) => (
                  <tr key={m}><td>{m}</td><td>{s.status}</td><td>{s.release_date ?? "–"}</td><td>{s.reason ? s.reason.slice(0, 180) : "–"}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </section>
      <div className="grid2">
        <section className="card">
          <h2>Builds</h2>
          <table><thead><tr><th>Build</th><th>Commit</th><th>What</th></tr></thead>
            <tbody>{S.builds.map((b) => <tr key={b.id}><td>{b.id}</td><td><code>{b.commit}</code></td><td>{b.summary.slice(0, 260)}{b.summary.length > 260 ? "…" : ""}</td></tr>)}</tbody>
          </table>
        </section>
        <section className="card">
          <h2>Pre-registration amendments</h2>
          <table><thead><tr><th>#</th><th>Date</th><th>When</th><th>What</th></tr></thead>
            <tbody>{S.amendments.map((a) => <tr key={a.id}><td>{a.id}</td><td>{a.date}</td><td>{a.when}</td><td>{a.title}</td></tr>)}</tbody>
          </table>
          {S.audits.map((a) => (
            <div key={a.id}><h3>{a.title}</h3><ul>{a.items.map((i) => <li key={i}>{i}</li>)}</ul></div>
          ))}
        </section>
      </div>
    </>
  );
}
