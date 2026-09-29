// Compile and validate the guided journey (site/content/journey.yaml) and the terminal tasks
// (site/content/tasks/*.yaml) into the content bundle. Build-time only: any problem fails the
// build (scripts/prebuild.mjs). Format: site/content/README.md, "The journey".
//
// Error explanations on task pages are reused, not rewritten:
//   `doctor: <key>`  -> the doctor's own fix message (site/content/doctor_fixes.json, exported
//                       from src/tsfm_rc/pipeline/doctor.py by `make lessons`);
//   `error: <text>`  -> the entry of site/content/errors.yaml whose `see` starts with <text>.
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { load as yamlLoad } from "js-yaml";

export const SITE_ACTIONS = {
  welcome: "/welcome",
  results: "/results",
  review: "/review",
};
export const CHECK_PARSERS = ["doctor", "study", "publish", "tests"];
export const OSES = ["macos", "windows", "linux"];
export const AUTO_SIGNALS = ["real_results"];

/** Sentences in a short text: ". ", "! ", "? " followed by a capital, plus the final one. */
function sentences(text) {
  const t = String(text ?? "").replace(/`[^`]*`/g, "x").replace(/\b(e\.g|i\.e|etc|vs)\./g, "$1");
  return t.trim() ? t.split(/[.!?](?=\s+[A-Z(])/).length : 0;
}

function validateTask(task, file, doctorFixes, errors) {
  const p = [];
  const where = `tasks/${file}`;
  if (task?.id !== file.replace(/\.ya?ml$/, "")) p.push(`${where}: id must equal the file name`);
  for (const f of ["title", "why", "time"]) if (!task?.[f]) p.push(`${where}: missing ${f}`);
  if (!Array.isArray(task?.commands) || !task.commands.length) p.push(`${where}: needs commands`);
  const commands = [];
  for (const [i, c] of (task?.commands ?? []).entries()) {
    const at = `${where} command ${i + 1}`;
    if (!c.title) p.push(`${at}: missing title`);
    const kinds = ["run", "run_os", "text"].filter((k) => c[k] !== undefined);
    if (kinds.length !== 1) p.push(`${at}: exactly one of run / run_os / text`);
    // run_os must give a command for every OS the command applies to
    if (c.run_os) for (const os of c.os ?? OSES) if (!c.run_os[os]) p.push(`${at}: run_os lacks ${os}`);
    for (const os of c.os ?? []) if (!OSES.includes(os)) p.push(`${at}: unknown os ${os}`);
    if (c.os_note) for (const os of Object.keys(c.os_note)) if (!OSES.includes(os)) p.push(`${at}: unknown os ${os} in os_note`);
    if ((c.run || c.run_os) && (!c.expect || !c.time)) p.push(`${at}: a command needs expect and time`);
    const errs = [];
    for (const e of c.errors ?? []) {
      if (e.doctor) {
        const d = doctorFixes[e.doctor];
        if (!d) p.push(`${at}: unknown doctor fix '${e.doctor}'`);
        else errs.push({ see: d.see, fix: d.fix, source: "make doctor" });
      } else if (e.error) {
        const hit = errors.find((x) => String(x.see).startsWith(e.error));
        if (!hit) p.push(`${at}: no entry of errors.yaml starts with '${e.error}'`);
        else errs.push({ see: hit.see, fix: `${hit.why} ${hit.fix}`, source: "errors.yaml" });
      } else if (e.see && e.fix) errs.push({ see: String(e.see), fix: String(e.fix), source: "task" });
      else p.push(`${at}: an error needs see + fix, doctor: <key> or error: <text>`);
    }
    commands.push({
      title: c.title, os: c.os ?? OSES, optional: !!c.optional, where: c.where ?? null,
      run: c.run ?? null, run_os: c.run_os ?? null, os_note: c.os_note ?? null, text: c.text ?? null,
      expect: c.expect ?? null, time: c.time ?? null, errors: errs,
    });
  }
  const ck = task?.check;
  if (!ck || !CHECK_PARSERS.includes(ck.parser) || !ck.prompt || !ck.success)
    p.push(`${where}: check needs parser (${CHECK_PARSERS.join("/")}), prompt and success`);
  if (ck?.auto && !AUTO_SIGNALS.includes(ck.auto)) p.push(`${where}: unknown auto signal ${ck.auto}`);
  if (ck?.start_button && !task.long_running) p.push(`${where}: start_button needs long_running: true`);
  return {
    problems: p,
    task: {
      id: task?.id, title: task?.title, why: task?.why, time: task?.time, note: task?.note ?? null,
      long_running: !!task?.long_running, before: task?.before ?? [], commands,
      check: { parser: ck?.parser, prompt: ck?.prompt, success: ck?.success, auto: ck?.auto ?? null, start_button: ck?.start_button ?? null },
    },
  };
}

/** Validate the raw journey.yaml against the lessons and tasks that exist. Returns problems. */
export function validateJourney(raw, { lessonIds, taskIds }) {
  const p = [];
  const phases = raw?.phases;
  if (!Array.isArray(phases) || !phases.length) return ["journey.yaml: needs a list of phases"];
  const welcome = raw?.welcome;
  if (!Array.isArray(welcome) || welcome.length !== 3 || welcome.some((w) => !w?.title || !w?.body))
    p.push("journey.yaml: welcome needs exactly 3 screens with title and body");
  const seen = new Set();
  const lessonUse = new Map();
  const taskUse = new Map();
  for (const ph of phases) {
    const at = `phase ${ph?.id ?? "?"}`;
    if (!/^P\d+$/.test(String(ph?.id))) p.push(`${at}: id must look like P0, P1, …`);
    if (seen.has(ph?.id)) p.push(`${at}: duplicate id`);
    for (const f of ["title", "goal", "why", "time", "done"]) if (!ph?.[f]) p.push(`${at}: missing ${f}`);
    if (ph?.goal && sentences(ph.goal) !== 1) p.push(`${at}: goal must be one sentence`);
    if (ph?.why && ![1, 2].includes(sentences(ph.why))) p.push(`${at}: why must be 1-2 sentences`);
    for (const r of ph?.requires ?? []) if (!seen.has(r)) p.push(`${at}: requires ${r}, which is not an earlier phase`);
    for (const r of ph?.parallel_with ?? []) if (!phases.some((x) => x.id === r)) p.push(`${at}: parallel_with unknown phase ${r}`);
    if (ph?.kind !== undefined && ph.kind !== "terminal") p.push(`${at}: kind must be 'terminal' if given`);
    if (!Array.isArray(ph?.steps) || !ph.steps.some((s) => !s?.optional)) p.push(`${at}: needs at least one required step`);
    for (const [i, s] of (ph?.steps ?? []).entries()) {
      const kinds = ["lesson", "task", "site"].filter((k) => s?.[k] !== undefined);
      if (kinds.length !== 1) {
        p.push(`${at} step ${i + 1}: exactly one of lesson / task / site`);
        continue;
      }
      if (s.lesson !== undefined) {
        if (!lessonIds.has(String(s.lesson))) p.push(`${at} step ${i + 1}: unknown lesson ${s.lesson}`);
        lessonUse.set(String(s.lesson), (lessonUse.get(String(s.lesson)) ?? 0) + 1);
      }
      if (s.task !== undefined) {
        if (!taskIds.has(s.task)) p.push(`${at} step ${i + 1}: unknown terminal task ${s.task}`);
        taskUse.set(s.task, (taskUse.get(s.task) ?? 0) + 1);
      }
      if (s.site !== undefined) {
        if (!(s.site in SITE_ACTIONS)) p.push(`${at} step ${i + 1}: unknown site action ${s.site}`);
        if (!s.title) p.push(`${at} step ${i + 1}: a site action needs a title`);
      }
      if (ph.kind === "terminal" && s.task === undefined) p.push(`${at}: a terminal phase has only terminal tasks`);
    }
    seen.add(ph?.id);
  }
  for (const id of lessonIds) if (lessonUse.get(id) !== 1) p.push(`lesson ${id} must appear exactly once in the journey (found ${lessonUse.get(id) ?? 0})`);
  for (const id of taskIds) if (taskUse.get(id) !== 1) p.push(`terminal task ${id} must appear exactly once in the journey (found ${taskUse.get(id) ?? 0})`);
  return p;
}

export function buildJourney(repo, lessons, errors) {
  const root = join(repo, "site", "content");
  const problems = [];
  const fixesPath = join(root, "doctor_fixes.json");
  const doctorFixes = existsSync(fixesPath) ? JSON.parse(readFileSync(fixesPath, "utf8")).fixes : {};
  if (!existsSync(fixesPath)) problems.push("site/content/doctor_fixes.json missing: run `make lessons`");
  const tasks = {};
  for (const file of readdirSync(join(root, "tasks")).filter((f) => f.endsWith(".yaml")).sort()) {
    const r = validateTask(yamlLoad(readFileSync(join(root, "tasks", file), "utf8")), file, doctorFixes, errors);
    problems.push(...r.problems);
    tasks[r.task.id] = r.task;
  }
  const raw = yamlLoad(readFileSync(join(root, "journey.yaml"), "utf8"));
  const lessonById = new Map(lessons.map((l) => [l.id, l]));
  problems.push(...validateJourney(raw, { lessonIds: new Set(lessonById.keys()), taskIds: new Set(Object.keys(tasks)) })
    .map((x) => `journey: ${x}`));
  const phases = (raw?.phases ?? []).map((ph) => ({
    id: ph.id, title: ph.title, kind: ph.kind ?? "site", goal: ph.goal, why: ph.why, time: ph.time, done: ph.done,
    note: ph.note ?? null, requires: ph.requires ?? [], parallel_with: ph.parallel_with ?? [], requires_real_results: !!ph.requires_real_results,
    steps: (ph.steps ?? []).map((s) => {
      if (s.lesson !== undefined) {
        const L = lessonById.get(String(s.lesson));
        return { key: `lesson:${s.lesson}`, kind: "lesson", ref: String(s.lesson), title: L ? `Lesson ${L.id}: ${L.title}` : String(s.lesson),
          minutes: L?.minutes ?? null, optional: !!s.optional, to: `/lessons/${s.lesson}` };
      }
      if (s.task !== undefined)
        return { key: `task:${s.task}`, kind: "task", ref: s.task, title: tasks[s.task]?.title ?? s.task, minutes: null,
          optional: !!s.optional, to: `/tasks/${s.task}` };
      return { key: `site:${s.site}`, kind: "site", ref: s.site, title: s.title, minutes: null, optional: !!s.optional,
        to: SITE_ACTIONS[s.site] ?? "/" };
    }),
  }));
  return { journey: { welcome: raw?.welcome ?? [], phases, tasks }, problems };
}
