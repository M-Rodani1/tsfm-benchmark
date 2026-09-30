// Small pieces of the guided journey shared by several pages. Everything they show comes from
// lib/journey.ts (computed from site/content/journey.yaml and the stored progress); this file
// only decides how it looks.
import { Link } from "react-router-dom";
import { content } from "../lib/content";
import { breadcrumb, type JourneyView, type NextAction, type PhaseView, type StepStatus } from "../lib/journey";
import { realResultsPublished } from "../lib/journeyState";
import { InlineMd } from "./Markdown";
import { Glyph, type GlyphKind } from "./Shell";

const STATUS_WORD: Record<StepStatus, string> = {
  done: "Done", next: "Next", in_progress: "In progress", locked: "Locked", optional: "Optional", upcoming: "To do",
};

/** A step's status as a word with its glyph (never colour alone). */
export function StatusPill({ status, testId, running = false, glyph = true }: { status: StepStatus; testId?: string; running?: boolean; glyph?: boolean }) {
  return (
    <span className="status-word" data-testid={testId} data-status={status}>
      {glyph && <Glyph kind={glyphFor(status, running)} />}
      {running ? "Running" : STATUS_WORD[status]}
    </span>
  );
}

export function glyphFor(status: StepStatus, running = false): GlyphKind {
  if (status === "done") return "done";
  if (running) return "running";
  if (status === "next") return "current";
  return "pending";
}

const METHOD_SHORT: Record<string, string> = { output: "checked from your output", "self-reported": "self-reported", auto: "detected on this site" };

function lessonRange(ids: string[]): string {
  if (ids.length === 1) return `Lesson ${ids[0]}`;
  return `Lessons ${ids[0]} to ${ids[ids.length - 1]}`;
}

/** One line under a phase in the rail: what it is, or where it stands. */
export function phaseLine(p: PhaseView, studyRunning: boolean): string {
  const required = p.steps.filter((s) => !s.optional);
  if (p.status === "done") {
    const task = required.length === 1 && required[0].kind === "task" ? required[0] : null;
    return task?.method && METHOD_SHORT[task.method] ? `Done, ${METHOD_SHORT[task.method]}` : "Done";
  }
  if (studyRunning && p.steps.some((s) => s.key === "task:run-study")) return "Running on your laptop";
  const lessons = required.filter((s) => s.kind === "lesson").map((s) => s.ref);
  const others = required.filter((s) => s.kind !== "lesson");
  if (lessons.length) {
    const done = required.filter((s) => s.kind === "lesson" && s.done).length;
    const extra = others.map((s) => (s.kind === "task" ? ", then a task on your laptop" : s.ref === "results" ? " and the Results page" : "")).join("");
    return `${lessonRange(lessons)}${extra}${done ? `, ${done} done` : ""}`;
  }
  if (p.locked && p.lockReason) return p.lockReason.replace(/^Unlocks after /, "After ").replace(/\.$/, "");
  return p.kind === "terminal" ? "On your laptop" : "";
}

/** The rail of Home and the other console pages: every phase, its glyph and one line. */
export function PathRail({ v }: { v: JourneyView }) {
  const current = v.phases.find((p) => p.status === "next")?.id ?? null;
  return (
    <nav aria-label="Your path" data-testid="path-summary">
      <div className="rail-head">
        <h2>Your path</h2>
        <span className="count num">{v.progress.done} of {v.progress.total} steps</span>
      </div>
      <ol className="phase-list">
        {v.phases.map((p) => {
          const running = v.studyRunning && p.steps.some((s) => s.key === "task:run-study");
          const isCurrent = p.id === current;
          const line = phaseLine(p, v.studyRunning);
          return (
            <li key={p.id} className={isCurrent ? "current" : ""} data-status={p.status}>
              <Link to={`/path#${p.id}`} aria-current={isCurrent ? "step" : undefined} data-testid={`rail-${p.id}`}>
                <Glyph kind={p.status === "done" ? "done" : running ? "running" : isCurrent ? "current" : "pending"} />
                <span className="phase-title">{p.title}</span>
                <span className="phase-line">
                  <span className="visually-hidden">{p.status === "done" ? "Done. " : running ? "Running. " : isCurrent ? "Current phase. " : ""}</span>
                  {line}
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
      <ul className="rail-links">
        <li><Link to="/path">Every step, with times</Link></li>
        <li><Link to="/welcome">Tour</Link></li>
        <li><Link to="/status">Research status</Link></li>
      </ul>
    </nav>
  );
}

/** The collapsed rail's label below 860px: "Your path: Phase 3 of 8, Foundations". */
export function pathToggleLabel(v: JourneyView): string {
  const p = v.phases.find((x) => x.status === "next") ?? v.phases.find((x) => x.status !== "done");
  if (!p) return `Your path: all ${v.phases.length} phases done`;
  return `Your path: Phase ${p.index} of ${v.phases.length}, ${p.title}`;
}

/** Where a lesson or task sits on the path: "Phase 3 · Foundations · lesson 2 of 4". */
export function phaseContext(stepKey: string): { text: string; phaseId: string } | null {
  const b = breadcrumb(content.journey, stepKey);
  if (!b) return null;
  const ph = content.journey.phases[b.phaseIndex];
  if (stepKey.startsWith("lesson:")) {
    const lessons = ph.steps.filter((s) => !s.optional && s.kind === "lesson");
    const at = lessons.findIndex((s) => s.key === stepKey);
    return { text: `Phase ${b.phaseIndex} · ${ph.title} · lesson ${at + 1} of ${lessons.length}`, phaseId: b.phaseId };
  }
  return { text: b.text, phaseId: b.phaseId };
}

export function Breadcrumb({ stepKey }: { stepKey: string }) {
  const b = phaseContext(stepKey);
  if (!b) return null;
  return (
    <nav className="lesson-context" aria-label="Where this is on your path" data-testid="breadcrumb">
      <Link to={`/path#${b.phaseId}`}>{b.text}</Link>
    </nav>
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
      <Link className="btn primary wide" to={to} data-testid="journey-next-button" data-step={next.stepKey ?? "done"}>
        {next.kind === "done" ? next.button : <span>Next step: <InlineMd text={label} /></span>}
      </Link>
      <span className="sub">On your path{next.kind !== "done" && next.minutes ? ` · ${next.minutes}` : ""}</span>
    </div>
  );
}

/** Lessons 09-10 and the Results page while the published results are synthetic. Never a lock. */
export function SyntheticBanner({ what }: { what: string }) {
  if (realResultsPublished()) return null;
  return (
    <div className="notice synthetic" data-testid="synthetic-banner">
      <span className="label">These results are SYNTHETIC.</span> {what[0].toUpperCase() + what.slice(1)} uses the committed fixture runs, which say
      nothing about markets. The real version appears when you <Link to="/tasks/run-study">run the study on your laptop (Phase 2)</Link> and{" "}
      <Link to="/tasks/publish">publish its results (Phase 5)</Link>. Everything here still works on the synthetic data.
    </div>
  );
}
