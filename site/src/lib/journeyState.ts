// The journey's link to stored progress: builds the snapshot lib/journey.ts works on, and
// records journey events (terminal task checked or self-reported, study started, tour seen,
// Results visited) in the table journey_state, which is local-first and synced like all others.
import { store as appStore, useStore } from "./app";
import { content, lessons, researchStatus } from "./content";
import type { LocalStore } from "./db";
import { computeJourney, type DoneMethod, type JourneyRecord, type JourneySnapshot, type JourneyView } from "./journey";
import { getProgress, lessonPlan, logEvent } from "./progress";
import type { ResearchStatus } from "./types";

/** A real run of the study is published on this site: the `default` run, non-synthetic
 * (publish.py labels a run synthetic unless its data source is yfinance or csv). Build-time
 * fact: it changes when a push of site/public/data/results makes Netlify rebuild the site. */
export function realResultsPublished(status: ResearchStatus = researchStatus): boolean {
  return status.runs.some((r) => r.run === "default" && !r.synthetic);
}

export function journeySnapshot(store: LocalStore, realResults = realResultsPublished()): JourneySnapshot {
  const snapLessons: JourneySnapshot["lessons"] = {};
  for (const L of lessons) {
    const p = getProgress(store, L);
    const plan = lessonPlan(store, L);
    snapLessons[L.id] = {
      status: p.status, title: L.title, stepCount: L.steps.length, minutesLeft: plan.minutesLeft,
      step: plan.step ? { id: plan.step.id, index: plan.stepIndex, title: plan.step.title } : null,
      touched: store.get("lesson_progress", L.id)?.updated_at ?? null,
    };
  }
  const records: Record<string, JourneyRecord> = {};
  for (const r of store.all<JourneyRecord>("journey_state")) records[r.id] = r.data;
  return { lessons: snapLessons, records, realResults };
}

export function journeyView(store: LocalStore = appStore): JourneyView {
  return computeJourney(content.journey, journeySnapshot(store));
}

export function useJourney(): JourneyView {
  useStore();
  return journeyView();
}

function put(store: LocalStore, key: string, patch: Partial<JourneyRecord>) {
  const prev = store.get<JourneyRecord>("journey_state", key)?.data;
  store.put<JourneyRecord>("journey_state", key, {
    step_key: key, status: "started", method: null, detail: "", started_at: null, done_at: null, ...prev, ...patch,
  });
}

export function markDone(store: LocalStore, key: string, method: DoneMethod, detail: string, sessionId: string | null = null, now = new Date()) {
  put(store, key, { status: "done", method, detail: detail.slice(0, 300), done_at: now.toISOString() });
  logEvent(store, sessionId, "journey_step_done", `${key} (${method})`, now);
}

export function markStarted(store: LocalStore, key: string, sessionId: string | null = null, now = new Date()) {
  const prev = store.get<JourneyRecord>("journey_state", key)?.data;
  if (prev?.status === "done") return;
  put(store, key, { status: "started", started_at: prev?.started_at ?? now.toISOString() });
  logEvent(store, sessionId, "journey_step_started", key, now);
}

/** Undo a self-reported or mistaken state (the record becomes a tombstone, synced as such). */
export function resetStep(store: LocalStore, key: string) {
  store.remove("journey_state", key);
}
