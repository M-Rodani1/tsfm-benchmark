// Learning progress: steps, activities, lesson completion, flashcards and the home-page plan.
import type { LocalStore } from "./db";
import { allFlashcards, lessons as allLessons } from "./content";
import { isDue, localDate, newCard, type CardState } from "./srs";
import type { Lesson, Step } from "./types";

export type ActivityState =
  | { kind: "predict"; answer: string | number; correct: boolean | null; at: string }
  | { kind: "python"; ok: boolean; at: string }
  | { kind: "checkpoint"; passed: boolean; at: string; hints_used: number; solution_viewed: boolean };

export interface LessonProgress {
  lesson_id: string;
  status: "not_started" | "in_progress" | "completed";
  current_step: string;
  completed_steps: string[];
  activities: Record<string, ActivityState>;
  prereq_override: boolean;
  started_at: string | null;
  completed_at: string | null;
}

export interface Draft {
  lesson_id: string;
  cell_id: string;
  code: string;
  hints_revealed: number;
  solution_viewed: boolean;
}

export interface SessionEvent { t: string; type: string; detail: string }

export function emptyProgress(lesson: Lesson): LessonProgress {
  return { lesson_id: lesson.id, status: "not_started", current_step: lesson.steps[0]?.id ?? "", completed_steps: [],
    activities: {}, prereq_override: false, started_at: null, completed_at: null };
}

export function getProgress(store: LocalStore, lesson: Lesson): LessonProgress {
  return { ...emptyProgress(lesson), ...(store.get<LessonProgress>("lesson_progress", lesson.id)?.data ?? {}) };
}

export function stepDone(step: Step, p: LessonProgress): boolean {
  return step.blocks.every((b) => {
    if (b.kind === "md") return true;
    const a = p.activities[b.id];
    if (!a) return false;
    if (a.kind === "python") return a.ok;
    if (a.kind === "checkpoint") return a.passed;
    return true; // any prediction counts: committing to a guess is the point
  });
}

export function percentDone(lesson: Lesson, p: LessonProgress): number {
  if (!lesson.steps.length) return 0;
  return Math.round((100 * lesson.steps.filter((s) => stepDone(s, p)).length) / lesson.steps.length);
}

export function missingPrerequisites(store: LocalStore, lesson: Lesson): string[] {
  return lesson.prerequisites.filter((id) => {
    const l = allLessons.find((x) => x.id === id);
    return !l || getProgress(store, l).status !== "completed";
  });
}

/** Add the lesson's cards to the review queue (due today); existing states are kept. */
export function addLessonCards(store: LocalStore, lesson: Lesson, now: Date): number {
  let added = 0;
  for (const c of lesson.flashcards) {
    if (!store.get("flashcard_state", c.id)) {
      store.put<CardState>("flashcard_state", c.id, newCard(c.id, lesson.id, localDate(now)));
      added++;
    }
  }
  return added;
}

export function logEvent(store: LocalStore, sessionId: string | null, type: string, detail: string, now = new Date()) {
  if (!sessionId) return;
  const rec = store.get<{ events: SessionEvent[] }>("session_log", sessionId);
  if (!rec) return;
  store.put("session_log", sessionId, { ...rec.data, events: [...(rec.data.events ?? []), { t: now.toISOString(), type, detail }] });
}

/** Record one activity; updates completed steps and, when every step is done, completes the lesson. */
export function recordActivity(store: LocalStore, lesson: Lesson, activityId: string, state: ActivityState,
  opts: { sessionId?: string | null; now?: Date } = {}): LessonProgress {
  const now = opts.now ?? new Date();
  const p = getProgress(store, lesson);
  const activities = { ...p.activities, [activityId]: state };
  // never downgrade a passed checkpoint or a successful run
  const prev = p.activities[activityId];
  if (prev?.kind === "checkpoint" && prev.passed && state.kind === "checkpoint" && !state.passed) activities[activityId] = { ...state, passed: true };
  if (prev?.kind === "python" && prev.ok && state.kind === "python" && !state.ok) activities[activityId] = prev;
  const next: LessonProgress = { ...p, activities, status: p.status === "not_started" ? "in_progress" : p.status,
    started_at: p.started_at ?? now.toISOString() };
  const before = new Set(p.completed_steps);
  next.completed_steps = lesson.steps.filter((s) => stepDone(s, next)).map((s) => s.id);
  for (const s of next.completed_steps) if (!before.has(s)) logEvent(store, opts.sessionId ?? null, "step_completed", `${lesson.id} · ${s}`, now);
  if (next.completed_steps.length === lesson.steps.length && p.status !== "completed") {
    next.status = "completed";
    next.completed_at = now.toISOString();
    const n = addLessonCards(store, lesson, now);
    logEvent(store, opts.sessionId ?? null, "lesson_completed", `${lesson.id} (${n} flashcards added)`, now);
  }
  store.put("lesson_progress", lesson.id, next);
  return next;
}

/** Remember the learner's position. Merely opening a lesson (first step, nothing done) does
 * not start it; moving to another step does. */
export function setCurrentStep(store: LocalStore, lesson: Lesson, stepId: string) {
  const p = getProgress(store, lesson);
  if (p.current_step === stepId) return;
  if (p.status === "not_started" && stepId === lesson.steps[0]?.id) return;
  store.put("lesson_progress", lesson.id, { ...p, current_step: stepId, status: p.status === "not_started" ? "in_progress" : p.status,
    started_at: p.started_at ?? new Date().toISOString() });
}

export function overridePrerequisites(store: LocalStore, lesson: Lesson) {
  store.put("lesson_progress", lesson.id, { ...getProgress(store, lesson), prereq_override: true });
}

export function dueCards(store: LocalStore, now: Date) {
  const today = localDate(now);
  const cards = new Map(allFlashcards().map((c) => [c.id, c]));
  return store
    .all<CardState>("flashcard_state")
    .filter((r) => isDue(r.data, today) && cards.has(r.id))
    .map((r) => ({ state: r.data, card: cards.get(r.id)! }))
    .sort((a, b) => (a.state.due < b.state.due ? -1 : a.state.due > b.state.due ? 1 : a.card.id.localeCompare(b.card.id)));
}

export interface Plan {
  lesson: Lesson;
  step: Step;
  stepIndex: number;
  minutesLeft: number;
  mode: "continue" | "start";
}

/** The next lesson step to do: the most recently touched unfinished lesson, else the first unfinished. */
export function nextLessonStep(store: LocalStore, lessons: Lesson[] = allLessons): Plan | null {
  const recs = lessons
    .map((l) => ({ l, rec: store.get<LessonProgress>("lesson_progress", l.id) }))
    .filter((x) => x.rec && x.rec.data.status === "in_progress")
    .sort((a, b) => (a.rec!.updated_at < b.rec!.updated_at ? 1 : -1));
  const pick = recs[0]?.l ?? lessons.find((l) => getProgress(store, l).status !== "completed");
  return pick ? lessonPlan(store, pick) : null;
}

/** Where to continue one lesson: the current step, or the first open step after it. */
export function lessonPlan(store: LocalStore, lesson: Lesson): Plan {
  const p = getProgress(store, lesson);
  let idx = Math.max(0, lesson.steps.findIndex((s) => s.id === p.current_step));
  if (stepDone(lesson.steps[idx], p)) {
    const firstOpen = lesson.steps.findIndex((s, i) => i >= idx && !stepDone(s, p));
    if (firstOpen >= 0) idx = firstOpen;
  }
  const remaining = lesson.steps.filter((s) => !stepDone(s, p)).length;
  const minutesLeft = Math.max(5, Math.round((lesson.minutes * remaining) / lesson.steps.length / 5) * 5);
  return { lesson, step: lesson.steps[idx], stepIndex: idx, minutesLeft, mode: p.status === "in_progress" ? "continue" : "start" };
}
