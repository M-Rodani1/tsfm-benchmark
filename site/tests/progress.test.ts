import { describe, expect, it } from "vitest";
import { lessons } from "../src/lib/content";
import { LocalStore, MemoryBackend } from "../src/lib/db";
import { dueCards, getProgress, missingPrerequisites, nextLessonStep, percentDone, recordActivity, type ActivityState } from "../src/lib/progress";

function completeLesson(store: LocalStore, id: string, now: Date) {
  const l = lessons.find((x) => x.id === id)!;
  for (const s of l.steps)
    for (const b of s.blocks) {
      if (b.kind === "md") continue;
      const at = now.toISOString();
      const st: ActivityState = b.kind === "python" ? { kind: "python", ok: true, at }
        : b.kind === "predict" ? { kind: "predict", answer: 0, correct: true, at }
        : { kind: "checkpoint", passed: true, at, hints_used: 0, solution_viewed: false };
      recordActivity(store, l, b.id, st, { now });
    }
  return l;
}

describe("lesson progress", () => {
  it("a step is done only when every activity is; completing all steps completes the lesson and queues its cards", async () => {
    const store = new LocalStore(new MemoryBackend());
    await store.init();
    const now = new Date("2026-04-01T10:00:00");
    const l = lessons[1];
    const first = l.steps[0];
    const act = first.blocks.find((b) => b.kind === "python")!;
    recordActivity(store, l, act.id, { kind: "python", ok: false, at: now.toISOString() }, { now });
    expect(getProgress(store, l).completed_steps).not.toContain(first.id);
    expect(getProgress(store, l).status).toBe("in_progress");
    completeLesson(store, l.id, now);
    const p = getProgress(store, l);
    expect(p.status).toBe("completed");
    expect(percentDone(l, p)).toBe(100);
    const due = dueCards(store, now);
    expect(due.map((d) => d.card.id).sort()).toEqual(l.flashcards.map((c) => c.id).sort());
  });

  it("a passed checkpoint is never downgraded by a later failed attempt", async () => {
    const store = new LocalStore(new MemoryBackend());
    await store.init();
    const l = lessons[0];
    const id = `${l.steps[l.steps.length - 1].id}.checkpoint1`;
    const at = new Date().toISOString();
    recordActivity(store, l, id, { kind: "checkpoint", passed: true, at, hints_used: 1, solution_viewed: false });
    recordActivity(store, l, id, { kind: "checkpoint", passed: false, at, hints_used: 1, solution_viewed: false });
    const a = getProgress(store, l).activities[id];
    expect(a.kind === "checkpoint" && a.passed).toBe(true);
  });

  it("home plan: continue the lesson in progress at its first open step; prerequisites are reported", async () => {
    const store = new LocalStore(new MemoryBackend());
    await store.init();
    expect(nextLessonStep(store)!.lesson.id).toBe("00");
    expect(nextLessonStep(store)!.mode).toBe("start");
    const now = new Date();
    completeLesson(store, "00", now);
    expect(nextLessonStep(store)!.lesson.id).toBe("01");
    const l4 = lessons.find((l) => l.id === "04")!;
    expect(missingPrerequisites(store, l4)).toEqual(["01", "02", "03"]);
    const s0 = l4.steps[0].blocks.find((b) => b.kind !== "md")!;
    recordActivity(store, l4, s0.id, { kind: "python", ok: true, at: now.toISOString() });
    const plan = nextLessonStep(store)!;
    expect(plan.lesson.id).toBe("04");
    expect(plan.mode).toBe("continue");
    expect(plan.stepIndex).toBe(1); // step 1 is done, so the plan moves on
    expect(plan.minutesLeft).toBeGreaterThan(0);
  });
});
