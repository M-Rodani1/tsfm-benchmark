// "Your path": the whole journey as a vertical roadmap (site/content/journey.yaml), with the
// status of every phase and step computed from your progress (lib/journey.ts).
import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { StatusPill } from "../components/Journey";
import { InlineMd } from "../components/Markdown";
import { useJourney } from "../lib/journeyState";

const METHOD: Record<string, string> = { output: "checked from pasted output", "self-reported": "self-reported", auto: "detected automatically", site: "" };

export function Path() {
  const v = useJourney();
  const { hash } = useLocation();
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView({ block: "start" });
  }, [hash]);
  return (
    <>
      <h1>Your path</h1>
      <p className="sub">
        The whole project, in order: what to do, why, and how long it takes. Lessons run in this browser; phases marked
        <em> on your laptop</em> run in a terminal. Phase 2 runs for hours on its own, so the lessons of phases 3 and 4 go on
        at the same time.
      </p>
      <section className="card" data-testid="path-progress">
        <div className="row">
          <strong>{v.progress.done} of {v.progress.total} steps done</strong>
          <span className="progress" style={{ flex: 1 }} aria-label={`${v.progress.percent}% done`}><span style={{ width: `${v.progress.percent}%` }} /></span>
          <span className="muted">{v.progress.percent}%</span>
        </div>
        <p style={{ marginBottom: 0 }}>Next: <Link to={v.next.to} data-testid="path-next"><InlineMd text={v.next.title} /></Link></p>
      </section>
      <ol className="roadmap">
        {v.phases.map((p) => (
          <li key={p.id} id={p.id} className={`road-phase ${p.status}`} data-testid={`phase-${p.id}`} data-status={p.status}>
            <div className="road-dot" aria-hidden="true">{p.status === "done" ? "✓" : p.index}</div>
            <div className="card">
              <div className="row">
                <h2 style={{ margin: 0 }}>Phase {p.index} · {p.title}</h2>
                {p.kind === "terminal" && <span className="status-tag terminal">⌨️ on your laptop</span>}
                <span className="spacer" />
                <StatusPill status={p.status} testId={`phase-status-${p.id}`} />
              </div>
              <p style={{ margin: "8px 0 4px" }}><strong><InlineMd text={p.goal} /></strong></p>
              <p className="sub" style={{ margin: 0 }}><InlineMd text={p.why} /> ⏱ {p.time}</p>
              {p.note && <p className="note"><strong>{p.note}</strong></p>}
              {p.parallel_with.length > 0 && (
                <p className="sub">Runs in parallel with {p.parallel_with.map((x) => `Phase ${x.slice(1)}`).join(" and ")}.</p>
              )}
              {p.locked && p.lockReason && <p className="sub" data-testid={`lock-${p.id}`}>🔒 {p.lockReason}</p>}
              <ol className="road-steps">
                {p.steps.map((s) => (
                  <li key={s.key} data-testid={`step-${s.key}`} data-status={s.status}>
                    <Link to={s.to}>{s.kind === "task" ? "⌨️ " : s.kind === "site" ? "🧭 " : "📘 "}<InlineMd text={s.title} /></Link>
                    {s.minutes ? <span className="sub"> · {s.minutes} min</span> : null}
                    <span className="spacer" />
                    {s.method && METHOD[s.method] && <span className="sub">{METHOD[s.method]} · </span>}
                    <StatusPill status={s.status} />
                  </li>
                ))}
              </ol>
              <p className="sub" style={{ marginBottom: 0 }}>Done when: <InlineMd text={p.done} /></p>
            </div>
          </li>
        ))}
      </ol>
    </>
  );
}
