// Small pieces of the guided journey shared by several pages. Everything they show comes from
// lib/journey.ts (computed from site/content/journey.yaml and the stored progress).
import { Link } from "react-router-dom";
import { content } from "../lib/content";
import { breadcrumb, type NextAction, type StepStatus } from "../lib/journey";
import { realResultsPublished } from "../lib/journeyState";
import { InlineMd } from "./Markdown";

const STATUS_LABEL: Record<StepStatus, string> = {
  done: "✓ done", next: "→ next", in_progress: "in progress", locked: "🔒 locked", optional: "optional", upcoming: "to do",
};

export function StatusPill({ status, testId }: { status: StepStatus; testId?: string }) {
  return <span className={`status-tag ${status}`} data-testid={testId} data-status={status}>{STATUS_LABEL[status]}</span>;
}

/** Home: the ONE thing to do next, with why and how long. */
export function NextStepCard({ next }: { next: NextAction }) {
  const phase = content.journey.phases.findIndex((p) => p.id === next.phaseId);
  return (
    <section className="card hero next-action" data-testid="next-action" data-step={next.stepKey ?? "done"}>
      <div className="sub">Do this next{phase >= 0 ? ` · Phase ${phase}: ${content.journey.phases[phase].title}` : ""}</div>
      <h2 style={{ marginTop: 6 }} data-testid="next-action-title"><InlineMd text={next.title} /></h2>
      <p className="why"><InlineMd text={next.why} /></p>
      {next.note && <p className="note" data-testid="next-action-note"><strong>{next.note}</strong></p>}
      <div className="row">
        <Link className="btn primary" to={next.to} data-testid="next-action-button">{next.button} →</Link>
        {next.minutes && <span className="muted">⏱ {next.minutes}</span>}
      </div>
      {next.alternative && (
        <p className="sub" style={{ marginBottom: 0 }}>
          <Link to={next.alternative.to} data-testid="next-action-alternative">{next.alternative.label}</Link>
        </p>
      )}
    </section>
  );
}

/** The single "Next step" button at the end of every lesson and task page. When this page is
 * itself the next step, it points at what finishes it (the open lesson step, or the check). */
export function NextStepButton({ next, here }: { next: NextAction; here: string }) {
  const self = next.stepKey === here && next.kind !== "done";
  const to = self && next.kind === "task" ? `${next.to}#check` : next.to;
  const label = self && next.kind === "task" ? "finish this step: paste your output in the check above" : next.title;
  return (
    <div className="journey-next" data-testid="journey-next">
      <span className="sub">Next step on your path{next.kind !== "done" && next.minutes ? ` · ${next.minutes}` : ""}</span>
      <Link className="btn primary" to={to} data-testid="journey-next-button" data-step={next.stepKey ?? "done"}>
        {next.kind === "done" ? next.button : <>Next step: <InlineMd text={label} /></>} →
      </Link>
    </div>
  );
}

export function Breadcrumb({ stepKey }: { stepKey: string }) {
  const b = breadcrumb(content.journey, stepKey);
  if (!b) return null;
  return (
    <nav className="breadcrumb" aria-label="Where this is on your path" data-testid="breadcrumb">
      <Link to={`/path#${b.phaseId}`}>{b.text}</Link>
    </nav>
  );
}

/** Lessons 09-10 and the Results page while the published results are synthetic. Never a lock. */
export function SyntheticBanner({ what }: { what: string }) {
  if (realResultsPublished()) return null;
  return (
    <div className="banner synthetic" data-testid="synthetic-banner">
      These results are SYNTHETIC: {what} uses the committed fixture runs, which say nothing about markets. The real version
      unlocks when you <Link to="/tasks/run-study">run the study on your laptop (Phase 2)</Link> and{" "}
      <Link to="/tasks/publish">publish its results (Phase 5)</Link>. Everything here still works on the synthetic data.
    </div>
  );
}

export function StudyRunningCard() {
  return (
    <section className="card study-running" data-testid="study-running">
      <strong>⏳ Study running on your laptop?</strong> Keep going with lessons. Come back here when it finishes:{" "}
      <Link to="/tasks/run-study">paste its output</Link>.
    </section>
  );
}
