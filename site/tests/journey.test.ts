// The guided journey: nextAction() and step statuses across the whole route, breadcrumbs, and
// build-time validation of site/content/journey.yaml and tasks/*.yaml.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { load as yamlLoad } from "js-yaml";
import { describe, expect, it } from "vitest";
import contentJson from "../src/generated/content.json";
import { breadcrumb, computeJourney, nextAction, type JourneyRecord, type JourneySnapshot, type LessonSnapshot } from "../src/lib/journey";
import type { ContentBundle } from "../src/lib/types";
// @ts-expect-error plain ESM build scripts
import { buildJourney, validateJourney } from "../scripts/journey.mjs";

const content = contentJson as unknown as ContentBundle;
const J = content.journey;
const IDS = content.lessons.map((l) => l.id);
const REPO = join(__dirname, "..", "..");

function lesson(status: LessonSnapshot["status"], stepIndex = 0, touched: string | null = null): LessonSnapshot {
  return { status, title: "t", step: status === "completed" ? null : { id: `s${stepIndex}`, index: stepIndex, title: `Step ${stepIndex + 1}` },
    stepCount: 6, minutesLeft: 30, touched };
}
function rec(key: string, status: "started" | "done", method: JourneyRecord["method"] = status === "done" ? "output" : null): JourneyRecord {
  return { step_key: key, status, method, detail: "", started_at: null, done_at: null };
}
function snap(opts: { done?: string[]; inProgress?: Record<string, number>; records?: JourneyRecord[]; real?: boolean } = {}): JourneySnapshot {
  const lessons: JourneySnapshot["lessons"] = {};
  for (const id of IDS) lessons[id] = lesson("not_started");
  for (const id of opts.done ?? []) lessons[id] = lesson("completed");
  for (const [id, step] of Object.entries(opts.inProgress ?? {})) lessons[id] = lesson("in_progress", step, `2026-09-29T0${step}:00:00Z`);
  return { lessons, records: Object.fromEntries((opts.records ?? []).map((r) => [r.step_key, r])), realResults: !!opts.real };
}
const range = (a: number, b: number) => IDS.filter((id) => Number(id) >= a && Number(id) <= b);
const welcome = rec("site:welcome", "done", "site");
const statusOf = (s: JourneySnapshot, key: string) => computeJourney(J, s).phases.flatMap((p) => p.steps).find((x) => x.key === key)!.status;

describe("nextAction() across the journey", () => {
  it("fresh user: the tour first, everything later is upcoming or locked", () => {
    const s = snap();
    const n = nextAction(J, s);
    expect([n.kind, n.stepKey, n.to]).toEqual(["site", "site:welcome", "/welcome"]);
    const v = computeJourney(J, s);
    expect(v.progress).toEqual({ done: 0, total: 17, percent: 0 });
    expect(statusOf(s, "site:welcome")).toBe("next");
    expect(statusOf(s, "lesson:00")).toBe("upcoming");
    expect(statusOf(s, "task:setup")).toBe("upcoming"); // never locked: recommended after lesson 00, not required
    expect(statusOf(s, "task:run-study")).toBe("locked"); // needs the laptop set up
    expect(statusOf(s, "task:publish")).toBe("locked");
    expect(statusOf(s, "lesson:09")).toBe("locked"); // needs real results (the lesson page itself stays open)
    expect(statusOf(s, "site:review")).toBe("optional");
    expect(v.phases.find((p) => p.id === "P6")!.lockReason).toMatch(/real results/);
    expect(v.studyRunning).toBe(false);
  });

  it("after the tour: lesson 00, then mid-lesson it continues at the open step", () => {
    expect(nextAction(J, snap({ records: [welcome] }))).toMatchObject({ kind: "lesson", stepKey: "lesson:00", button: "Start lesson 00" });
    const mid = nextAction(J, snap({ records: [welcome], inProgress: { "00": 1 } }));
    expect(mid).toMatchObject({ kind: "lesson", button: "Continue lesson 00", to: "/lessons/00?step=s1" });
    expect(mid.title).toContain("step 2 of 6");
  });

  it("finishing lesson 00 makes the laptop setup (P1) next, with a lesson as the alternative", () => {
    const n = nextAction(J, snap({ records: [welcome], done: ["00"] }));
    expect([n.kind, n.stepKey, n.phaseId, n.to]).toEqual(["task", "task:setup", "P1", "/tasks/setup"]);
    expect(n.alternative).toEqual({ label: "Not at your laptop? Start lesson 01 instead", to: "/lessons/01" });
    // even when another lesson was started first, P1 stays the recommendation
    expect(nextAction(J, snap({ records: [welcome], done: ["00"], inProgress: { "03": 2 } })).alternative?.to).toBe("/lessons/03");
  });

  it("P1 done: launch the study (P2) right away, and say to keep learning while it runs", () => {
    const s = snap({ records: [welcome, rec("task:setup", "done")], done: ["00"] });
    const n = nextAction(J, s);
    expect([n.stepKey, n.phaseId]).toEqual(["task:run-study", "P2"]);
    expect(n.note).toBe("Start this now and keep learning while it runs.");
    expect(statusOf(s, "task:run-study")).toBe("next");
  });

  it("P2 running: lessons of P3-P4 continue in parallel; the study shows as in progress", () => {
    const records = [welcome, rec("task:setup", "done"), rec("task:run-study", "started")];
    const s = snap({ records, done: ["00"] });
    const v = computeJourney(J, s);
    expect(v.studyRunning).toBe(true);
    expect(v.next).toMatchObject({ kind: "lesson", stepKey: "lesson:01" });
    expect(statusOf(s, "task:run-study")).toBe("in_progress");
    expect(statusOf(s, "task:publish")).toBe("locked"); // the study has not finished
    // mid-lesson: the lesson touched last wins
    const s2 = snap({ records, done: ["00", "01", "02"], inProgress: { "05": 1, "03": 3 } });
    expect(nextAction(J, s2).stepKey).toBe("lesson:03");
    // every lesson available before real results done: check on the study
    const s3 = snap({ records, done: range(0, 8) });
    expect(nextAction(J, s3)).toMatchObject({ stepKey: "task:run-study", title: "Check on your study", button: "Paste the output" });
  });

  it("study confirmed finished: publish (P5) comes before more lessons", () => {
    const s = snap({ records: [welcome, rec("task:setup", "done"), rec("task:run-study", "done")], done: ["00"] });
    expect(nextAction(J, s)).toMatchObject({ stepKey: "task:publish", phaseId: "P5" });
    expect(statusOf(s, "task:publish")).toBe("next");
  });

  it("results published: P1, P2 and P5 are auto-detected, P6 unlocks after the lessons", () => {
    const s = snap({ records: [welcome], done: ["00"], real: true });
    const v = computeJourney(J, s);
    for (const k of ["task:setup", "task:run-study", "task:publish"]) {
      const st = v.phases.flatMap((p) => p.steps).find((x) => x.key === k)!;
      expect([k, st.status, st.method]).toEqual([k, "done", "auto"]);
    }
    expect(v.next.stepKey).toBe("lesson:01"); // P3-P4 still to do
    const s2 = snap({ records: [welcome], done: range(0, 8), real: true });
    expect(nextAction(J, s2)).toMatchObject({ stepKey: "lesson:09", phaseId: "P6" });
    expect(statusOf(s2, "lesson:09")).toBe("next");
    const s3 = snap({ records: [welcome], done: range(0, 9), real: true });
    expect(nextAction(J, s3)).toMatchObject({ stepKey: "site:results", to: "/results" });
    const s4 = snap({ records: [welcome, rec("site:results", "done", "site")], done: range(0, 9), real: true });
    expect(nextAction(J, s4).stepKey).toBe("lesson:10");
    const s5 = snap({ records: [welcome, rec("site:results", "done", "site")], done: range(0, 10), real: true });
    expect(nextAction(J, s5)).toMatchObject({ stepKey: "task:audit", phaseId: "P7" });
  });

  it("pushed but the site has not rebuilt: wait, do not unlock P6", () => {
    const records = [welcome, rec("task:setup", "done"), rec("task:run-study", "done"), rec("task:publish", "done", "self-reported")];
    const s = snap({ records, done: range(0, 8) });
    expect(nextAction(J, s)).toMatchObject({ stepKey: "task:publish", title: "Wait for the site to show your results" });
    expect(statusOf(s, "lesson:09")).toBe("locked");
  });

  it("all done: finished, 100%", () => {
    const records = [welcome, rec("site:results", "done", "site"), rec("task:audit", "done")];
    const s = snap({ records, done: IDS, real: true });
    const v = computeJourney(J, s);
    expect(v.next.kind).toBe("done");
    expect(v.progress).toEqual({ done: 17, total: 17, percent: 100 });
    expect(v.phases.every((p) => p.status === "done")).toBe(true);
    expect(v.phases.flatMap((p) => p.steps).filter((x) => x.status === "next")).toEqual([]);
  });

  it("exactly one step is ever 'next', and it is the one nextAction() names", () => {
    const cases = [snap(), snap({ records: [welcome] }), snap({ records: [welcome], done: ["00"] }),
      snap({ records: [welcome, rec("task:setup", "done"), rec("task:run-study", "started")], done: ["00", "01"] }),
      snap({ records: [welcome], done: range(0, 9), real: true })];
    for (const s of cases) {
      const v = computeJourney(J, s);
      const nexts = v.phases.flatMap((p) => p.steps).filter((x) => x.status === "next");
      expect(nexts.map((x) => x.key)).toEqual([v.next.stepKey]);
    }
  });

  it("self-reported steps count as done and are labelled", () => {
    const s = snap({ records: [welcome, rec("task:setup", "done", "self-reported")], done: ["00"] });
    const st = computeJourney(J, s).phases[1].steps[0];
    expect([st.status, st.method]).toEqual(["done", "self-reported"]);
  });
});

describe("breadcrumbs", () => {
  it("names phase, title and position among the required steps", () => {
    expect(breadcrumb(J, "lesson:02")?.text).toBe("Phase 3 · Foundations · step 2 of 4");
    expect(breadcrumb(J, "lesson:08")?.text).toBe("Phase 4 · Models and statistics · step 4 of 4");
    expect(breadcrumb(J, "task:setup")?.text).toBe("Phase 1 · Set up your laptop · step 1 of 1");
    expect(breadcrumb(J, "lesson:00")?.text).toBe("Phase 0 · Start here · step 2 of 2");
    expect(breadcrumb(J, "site:review")).toBeNull(); // optional steps are not counted
  });
});

describe("journey.yaml validation (build time)", () => {
  const raw = yamlLoad(readFileSync(join(REPO, "site", "content", "journey.yaml"), "utf8")) as { phases: Record<string, unknown>[] };
  const ctx = { lessonIds: new Set(IDS), taskIds: new Set(Object.keys(J.tasks)) };
  const clone = () => JSON.parse(JSON.stringify(raw));

  it("the committed journey and tasks are valid and cover every lesson and task exactly once", () => {
    expect(validateJourney(raw, ctx)).toEqual([]);
    const built = buildJourney(REPO, content.lessons, content.errors);
    expect(built.problems).toEqual([]);
    expect(built.journey.phases.map((p: { id: string }) => p.id)).toEqual(["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]);
    expect(J.phases.find((p) => p.id === "P2")!.note).toBe("Start this now and keep learning while it runs.");
  });

  it("rejects unknown lessons, tasks and site actions, duplicates and gaps", () => {
    const a = clone();
    a.phases[3].steps[0] = { lesson: "42" };
    const pa = validateJourney(a, ctx);
    expect(pa).toContain("phase P3 step 1: unknown lesson 42");
    expect(pa).toContain("lesson 01 must appear exactly once in the journey (found 0)");
    const b = clone();
    b.phases[1].steps = [{ task: "setup" }, { task: "nope" }];
    expect(validateJourney(b, ctx)).toContain("phase P1 step 2: unknown terminal task nope");
    const c = clone();
    c.phases[0].steps[0] = { site: "dance", title: "x" };
    expect(validateJourney(c, ctx)).toContain("phase P0 step 1: unknown site action dance");
    const d = clone();
    d.phases[4].steps.push({ lesson: "01" });
    expect(validateJourney(d, ctx)).toContain("lesson 01 must appear exactly once in the journey (found 2)");
  });

  it("rejects missing fields, multi-sentence goals, bad ordering and malformed steps", () => {
    const a = clone();
    delete a.phases[2].why;
    a.phases[2].goal = "One sentence. And another one.";
    const pa = validateJourney(a, ctx);
    expect(pa).toContain("phase P2: missing why");
    expect(pa).toContain("phase P2: goal must be one sentence");
    const b = clone();
    b.phases[1].requires = ["P7"];
    expect(validateJourney(b, ctx)).toContain("phase P1: requires P7, which is not an earlier phase");
    const c = clone();
    c.phases[1].steps = [{ task: "setup", lesson: "01" }];
    expect(validateJourney(c, ctx)).toContain("phase P1 step 1: exactly one of lesson / task / site");
    const d = clone();
    d.phases[1].steps = [{ lesson: "01" }, { task: "setup" }];
    d.phases[3].steps = d.phases[3].steps.slice(1);
    expect(validateJourney(d, ctx)).toContain("phase P1: a terminal phase has only terminal tasks");
    const e = clone();
    (e as { welcome: unknown[] }).welcome = [];
    expect(validateJourney(e, ctx)).toContain("journey.yaml: welcome needs exactly 3 screens with title and body");
  });
});
