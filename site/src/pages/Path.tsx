// "Your path": the whole journey in order (site/content/journey.yaml), with the status of every
// phase and step computed from your progress (lib/journey.ts).
import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { glyphFor, StatusPill } from "../components/Journey";
import { InlineMd } from "../components/Markdown";
import { Glyph, Shell } from "../components/Shell";
import { useJourney } from "../lib/journeyState";

const METHOD: Record<string, string> = { output: "checked from pasted output", "self-reported": "self-reported", auto: "detected automatically", site: "" };
const KIND: Record<string, string> = { lesson: "Lesson", task: "Laptop", site: "This site" };

export function Path() {
  const v = useJourney();
  const { hash } = useLocation();
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView({ block: "start" });
  }, [hash]);
  return (
    <Shell>
      <div className="content center">
        <h1>Your path</h1>
        <p className="lede">
          The whole project, in order: what to do, why, and how long it takes. Lessons run in this browser; phases marked
          <em> on your laptop</em> run in a terminal. Phase 2 runs for hours on its own, so the lessons of phases 3 and 4 go on
          at the same time.
        </p>
        <div data-testid="path-progress">
          <div className="path-progress">
            <strong className="num">{v.progress.done} of {v.progress.total} steps done</strong>
            <span className="bar" role="progressbar" aria-label="Steps done" aria-valuenow={v.progress.percent} aria-valuemin={0} aria-valuemax={100}>
              <span style={{ width: `${v.progress.percent}%` }} />
            </span>
            <span className="muted num">{v.progress.percent}%</span>
          </div>
          <p className="sub">Next: <Link to={v.next.to} data-testid="path-next"><InlineMd text={v.next.title} /></Link></p>
        </div>
        <ol className="roadmap">
          {v.phases.map((p) => {
            const running = v.studyRunning && p.steps.some((s) => s.key === "task:run-study");
            return (
              <li key={p.id} id={p.id} className={`road-phase ${p.status}`} data-testid={`phase-${p.id}`} data-status={p.status}>
                <Glyph kind={glyphFor(p.status, running)} />
                <div>
                  <div className="row">
                    <h2>Phase {p.index} · {p.title}</h2>
                    <StatusPill status={p.status} testId={`phase-status-${p.id}`} running={running} glyph={false} />
                  </div>
                  <p className="phase-meta">{p.kind === "terminal" ? "On your laptop · " : ""}{p.time}
                    {p.parallel_with.length > 0 && ` · runs alongside ${p.parallel_with.map((x) => `Phase ${x.slice(1)}`).join(" and ")}`}</p>
                  <p className="goal"><InlineMd text={p.goal} /></p>
                  <p className="sub"><InlineMd text={p.why} /></p>
                  {p.note && <p className="next-note">{p.note}</p>}
                  {p.locked && p.lockReason && <p className="sub" data-testid={`lock-${p.id}`}>Locked: {p.lockReason}</p>}
                  <ol className="road-steps">
                    {p.steps.map((s) => (
                      <li key={s.key} data-testid={`step-${s.key}`} data-status={s.status}>
                        <span className="kind">{KIND[s.kind]}</span>
                        <Link to={s.to}><InlineMd text={s.title} /></Link>
                        {s.minutes ? <span className="how num">{s.minutes} min</span> : null}
                        {s.method && METHOD[s.method] && <span className="how">{METHOD[s.method]}</span>}
                        <StatusPill status={s.status} running={running && s.key === "task:run-study"} />
                      </li>
                    ))}
                  </ol>
                  <p className="small-text">Done when: <InlineMd text={p.done} /></p>
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </Shell>
  );
}
