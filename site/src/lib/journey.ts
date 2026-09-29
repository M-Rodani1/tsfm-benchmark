// The guided journey: status of every step and the single next action. Pure functions of a
// snapshot (no store, no DOM), so every situation can be tested directly (tests/journey.test.ts).
// The snapshot is built from the stored progress by lib/journeyState.ts.
//
// Step status
//   done         lesson completed; terminal task checked (pasted output), self-reported or
//                auto-detected; site action performed
//   next         the step nextAction() points to (exactly one)
//   in_progress  a lesson started, or a long-running task started (the study on your laptop)
//   locked       its phase needs something not done yet (`requires`, or real results)
//   optional     not needed to finish its phase
//   upcoming     none of the above: available, just not the recommended next step
// Ordering (journey.yaml): P0, then P1 and P2 at once (P2 runs unattended), P3-P4 in parallel
// with P2, P5 once the study has finished, P6-P7 once real results are published.
import type { JourneyDef, JourneyStepDef, PhaseDef } from "./types";

export type StepStatus = "done" | "next" | "in_progress" | "locked" | "optional" | "upcoming";
export type DoneMethod = "output" | "self-reported" | "site" | "auto";

/** One stored record per journey step that has state (table journey_state; id = step key). */
export interface JourneyRecord {
  step_key: string;
  status: "started" | "done";
  method: DoneMethod | null;
  detail: string;
  started_at: string | null;
  done_at: string | null;
}

export interface LessonSnapshot {
  status: "not_started" | "in_progress" | "completed";
  title: string;
  /** Where to continue: the first open step (or the step the learner is on). */
  step: { id: string; index: number; title: string } | null;
  stepCount: number;
  minutesLeft: number;
  /** ISO time of the last change, to pick the lesson the learner touched last. */
  touched: string | null;
}

export interface JourneySnapshot {
  lessons: Record<string, LessonSnapshot>;
  records: Record<string, JourneyRecord>;
  /** A non-synthetic run of the study (`default`) is published on this site. */
  realResults: boolean;
}

export interface StepView extends JourneyStepDef {
  status: StepStatus;
  done: boolean;
  method: DoneMethod | null;
  detail: string;
}

export interface PhaseView extends Omit<PhaseDef, "steps"> {
  index: number;
  status: Exclude<StepStatus, "optional">;
  locked: boolean;
  lockReason: string | null;
  steps: StepView[];
}

export interface NextAction {
  kind: "lesson" | "task" | "site" | "done";
  stepKey: string | null;
  phaseId: string | null;
  title: string;
  why: string;
  minutes: string;
  to: string;
  button: string;
  note: string | null;
  /** A secondary suggestion (e.g. a lesson while the laptop task waits). */
  alternative: { label: string; to: string } | null;
}

export interface JourneyView {
  phases: PhaseView[];
  next: NextAction;
  progress: { done: number; total: number; percent: number };
  /** The study was started on the laptop and has not been confirmed finished. */
  studyRunning: boolean;
}

const PARALLEL_LESSONS = ["01", "02", "03", "04", "05", "06", "07", "08"];

export function stepDone(step: JourneyStepDef, s: JourneySnapshot, def: JourneyDef): { done: boolean; method: DoneMethod | null } {
  if (step.kind === "lesson") return { done: s.lessons[step.ref]?.status === "completed", method: null };
  const rec = s.records[step.key];
  if (rec?.status === "done") return { done: true, method: rec.method };
  if (step.kind === "task" && def.tasks[step.ref]?.check.auto === "real_results" && s.realResults) return { done: true, method: "auto" };
  return { done: false, method: null };
}

function started(step: JourneyStepDef, s: JourneySnapshot): boolean {
  if (step.kind === "lesson") return s.lessons[step.ref]?.status === "in_progress";
  return s.records[step.key]?.status === "started";
}

function findStep(def: JourneyDef, key: string): { phase: PhaseDef; step: JourneyStepDef } | null {
  for (const phase of def.phases) for (const step of phase.steps) if (step.key === key) return { phase, step };
  return null;
}

function lessonAction(def: JourneyDef, s: JourneySnapshot, id: string): NextAction {
  const f = findStep(def, `lesson:${id}`)!;
  const L = s.lessons[id];
  const cont = L?.status === "in_progress" && L.step;
  const to = L?.step ? `/lessons/${id}?step=${L.step.id}` : `/lessons/${id}`;
  return {
    kind: "lesson", stepKey: f.step.key, phaseId: f.phase.id,
    title: cont ? `Continue lesson ${id}: step ${L.step!.index + 1} of ${L.stepCount}, ${L.step!.title}` : `Lesson ${id}: ${L?.title ?? f.step.title}`,
    why: f.phase.why,
    minutes: `about ${L ? L.minutesLeft : f.step.minutes ?? 60} min`,
    to, button: cont ? `Continue lesson ${id}` : `Start lesson ${id}`, note: null, alternative: null,
  };
}

function taskAction(def: JourneyDef, key: string, extra: Partial<NextAction> = {}): NextAction {
  const f = findStep(def, key)!;
  const t = def.tasks[f.step.ref];
  return {
    kind: "task", stepKey: key, phaseId: f.phase.id, title: t.title, why: t.why, minutes: t.time, to: f.step.to,
    button: `Open the ${f.phase.kind === "terminal" ? "terminal " : ""}steps`, note: t.note ?? f.phase.note, alternative: null, ...extra,
  };
}

function siteAction(def: JourneyDef, key: string, extra: Partial<NextAction> = {}): NextAction {
  const f = findStep(def, key)!;
  return {
    kind: "site", stepKey: key, phaseId: f.phase.id, title: f.step.title, why: f.phase.why,
    minutes: key === "site:welcome" ? "1 min" : "about 30 min", to: f.step.to, button: f.step.title, note: null, alternative: null, ...extra,
  };
}

/** The next lesson of P3-P4: the one touched last if any is in progress, else the first unfinished. */
function nextParallelLesson(s: JourneySnapshot): string | null {
  const open = PARALLEL_LESSONS.filter((id) => s.lessons[id] && s.lessons[id].status !== "completed");
  const inProgress = open.filter((id) => s.lessons[id].status === "in_progress")
    .sort((a, b) => ((s.lessons[b].touched ?? "") > (s.lessons[a].touched ?? "") ? 1 : -1));
  return inProgress[0] ?? open[0] ?? null;
}

export function nextAction(def: JourneyDef, s: JourneySnapshot): NextAction {
  const done = (key: string) => {
    const f = findStep(def, key);
    return f ? stepDone(f.step, s, def).done : false;
  };
  const lessonDone = (id: string) => s.lessons[id]?.status === "completed";
  const lesson = nextParallelLesson(s);
  const alt = lesson ? { label: `Not at your laptop? ${s.lessons[lesson].status === "in_progress" ? "Continue" : "Start"} lesson ${lesson} instead`,
    to: `/lessons/${lesson}` } : null;

  if (!done("site:welcome")) return siteAction(def, "site:welcome", { button: "Start the tour", why: "Three short screens: the question, how this site works, and the route to a finished study." });
  if (!lessonDone("00")) return lessonAction(def, s, "00");
  if (!done("task:setup")) return taskAction(def, "task:setup", { alternative: alt });
  const study = findStep(def, "task:run-study")!.step;
  const studyDone = done("task:run-study");
  if (!studyDone && !started(study, s)) return taskAction(def, "task:run-study", { alternative: alt });
  if (studyDone && !done("task:publish")) return taskAction(def, "task:publish");
  if (lesson) return lessonAction(def, s, lesson);
  if (!studyDone)
    return taskAction(def, "task:run-study", {
      title: "Check on your study",
      why: "You have done every lesson you can before the real results exist. When `make reproduce` has finished, paste its output to confirm it.",
      minutes: "a few minutes, once it has finished", button: "Paste the output", note: null,
    });
  if (!s.realResults)
    return taskAction(def, "task:publish", {
      title: "Wait for the site to show your results",
      why: "Your results are marked as pushed, but this site does not show a real run yet. Netlify rebuilds 2–4 minutes after a push; reload then. If nothing changes, check the push (command 4).",
      minutes: "2–4 min", button: "Open the publish steps", note: null,
    });
  if (!lessonDone("09")) return lessonAction(def, s, "09");
  if (!done("site:results")) return siteAction(def, "site:results", { button: "Open the Results page" });
  if (!lessonDone("10")) return lessonAction(def, s, "10");
  if (!done("task:audit")) return taskAction(def, "task:audit");
  return {
    kind: "done", stepKey: null, phaseId: null, title: "You have finished the journey",
    why: "Your study is published, read and written up, and the repository is with the auditor. Keep your flashcards fresh in Review.",
    minutes: "", to: "/review", button: "Review flashcards", note: null, alternative: null,
  };
}

export function computeJourney(def: JourneyDef, s: JourneySnapshot): JourneyView {
  const next = nextAction(def, s);
  const phaseDone = new Map<string, boolean>();
  const phases: PhaseView[] = [];
  let doneCount = 0;
  let total = 0;
  for (const [index, ph] of def.phases.entries()) {
    const missing = ph.requires.filter((r) => !phaseDone.get(r));
    const needsReal = ph.requires_real_results && !s.realResults;
    const locked = missing.length > 0 || needsReal;
    const lockReason = needsReal ? "Unlocks when the real results are published (phases 2 and 5)."
      : missing.length ? `Unlocks after ${missing.map((m) => def.phases.find((p) => p.id === m)?.title ?? m).join(" and ")}.` : null;
    const steps: StepView[] = ph.steps.map((st) => {
      const d = stepDone(st, s, def);
      const rec = s.records[st.key];
      let status: StepStatus;
      if (d.done) status = "done";
      else if (st.key === next.stepKey) status = "next";
      else if (started(st, s)) status = "in_progress";
      else if (locked) status = "locked";
      else if (st.optional) status = "optional";
      else status = "upcoming";
      if (!st.optional) {
        total++;
        if (d.done) doneCount++;
      }
      return { ...st, status, done: d.done, method: d.method, detail: rec?.detail ?? "" };
    });
    const required = steps.filter((x) => !x.optional);
    const isDone = required.every((x) => x.done);
    phaseDone.set(ph.id, isDone);
    const status: PhaseView["status"] = isDone ? "done" : steps.some((x) => x.status === "next") ? "next"
      : steps.some((x) => x.status === "in_progress" || x.done) ? "in_progress" : locked ? "locked" : "upcoming";
    const { steps: _defSteps, ...rest } = ph;
    phases.push({ ...rest, index, status, locked, lockReason, steps });
  }
  const run = findStep(def, "task:run-study");
  const studyRunning = !!run && started(run.step, s) && !stepDone(run.step, s, def).done;
  return { phases, next, progress: { done: doneCount, total, percent: total ? Math.round((100 * doneCount) / total) : 0 }, studyRunning };
}

/** "Phase 3 · Foundations · step 2 of 4" for a lesson or task page. Optional steps are not counted. */
export function breadcrumb(def: JourneyDef, key: string): { text: string; phaseId: string; phaseIndex: number } | null {
  for (const [i, ph] of def.phases.entries()) {
    const required = ph.steps.filter((x) => !x.optional);
    const at = required.findIndex((x) => x.key === key);
    if (at >= 0) return { text: `Phase ${i} · ${ph.title} · step ${at + 1} of ${required.length}`, phaseId: ph.id, phaseIndex: i };
  }
  return null;
}
