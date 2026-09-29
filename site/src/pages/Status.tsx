import { Shell, Glyph } from "../components/Shell";
import { TerminalTaskCard } from "../components/TerminalTaskCard";
import { researchStatus as S } from "../lib/content";

export function Status() {
  return (
    <Shell>
      <div className="content wide center">
        <h1>Research status</h1>
        <p className="lede">
          Generated when the site is built, from <code>docs/BUILD-REPORT.md</code>, the amendments in <code>docs/PREREGISTRATION.md</code> and the
          published results{S.generated_from.commit ? <> (commit <code>{S.generated_from.commit.slice(0, 12)}</code>)</> : null}.
        </p>
        <section className="section" data-testid="phases" aria-labelledby="phases-title">
          <h2 id="phases-title">Research phases</h2>
          <ol className="road-steps">
            {S.phases.map((p) => (
              <li key={p.id} data-status={p.status} style={{ alignItems: "flex-start", flexWrap: "nowrap" }}>
                <Glyph kind={p.status === "done" ? "done" : "pending"} />
                <div><strong>{p.title}</strong><div className="sub">{p.status === "done" ? "Done. " : "Pending. "}{p.detail}</div></div>
              </li>
            ))}
          </ol>
        </section>
        {S.terminal_tasks.map((t) => <TerminalTaskCard key={t.id} task={t} />)}
        <section className="section" aria-labelledby="models-title">
          <h2 id="models-title">Models, per published run</h2>
          {S.runs.map((r) => (
            <div key={r.run} style={{ marginBottom: 24 }}>
              <h3>{r.run} {r.synthetic && <span className="small-text">· {r.label}</span>}</h3>
              <div className="prov">version {r.version} · published {r.published_utc} · commit {String(r.provenance.git_commit ?? "?").slice(0, 12)}</div>
              <table className="stack">
                <thead><tr><th scope="col">Model</th><th scope="col">Status</th><th scope="col">Documented release</th><th scope="col">Reason</th></tr></thead>
                <tbody>
                  {Object.entries(r.model_status).map(([m, s]) => (
                    <tr key={m}><th scope="row">{m}</th><td data-label="Status">{s.status}</td><td data-label="Documented release">{s.release_date ?? "–"}</td>
                      <td data-label="Reason">{s.reason ? s.reason.slice(0, 180) : "–"}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </section>
        <div className="two-col">
          <section className="section" aria-labelledby="builds-title">
            <h2 id="builds-title">Builds</h2>
            <table className="stack compact"><thead><tr><th scope="col">Build</th><th scope="col">Commit</th><th scope="col">What</th></tr></thead>
              <tbody>{S.builds.map((b) => <tr key={b.id}><th scope="row">{b.id}</th><td data-label="Commit"><code>{b.commit}</code></td>
                <td data-label="What">{b.summary.slice(0, 260)}{b.summary.length > 260 ? "…" : ""}</td></tr>)}</tbody>
            </table>
          </section>
          <section className="section" aria-labelledby="amend-title">
            <h2 id="amend-title">Pre-registration amendments</h2>
            <table className="stack compact"><thead><tr><th scope="col">#</th><th scope="col">Date</th><th scope="col">When</th><th scope="col">What</th></tr></thead>
              <tbody>{S.amendments.map((a) => <tr key={a.id}><th scope="row">{a.id}</th><td data-label="Date">{a.date}</td><td data-label="When">{a.when}</td>
                <td data-label="What">{a.title}</td></tr>)}</tbody>
            </table>
            {S.audits.map((a) => (
              <div key={a.id}><h3>{a.title}</h3><ul>{a.items.map((i) => <li key={i}>{i}</li>)}</ul></div>
            ))}
          </section>
        </div>
      </div>
    </Shell>
  );
}
