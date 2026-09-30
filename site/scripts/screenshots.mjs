// Screenshots of the design at 1440, 1024 and 390 px, light and dark (site/docs/screenshots).
// Usage (from site/, after `npm run build`):
//   node scripts/screenshots.mjs                 # states reachable with the committed data
//   node scripts/screenshots.mjs --simulated     # Home once real results are published / all done
// The --simulated run needs a build whose status.json contains a real `default` run; this script
// makes one in a temporary folder (dist-simulated/) and never touches the committed data. Those
// screenshots are named *-SIMULATED and listed as such in site/docs/screenshots/README.md.
/* global window, document -- used inside page.evaluate() callbacks, which run in the browser */
import { spawn, execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..");
const OUT = join(SITE, "docs", "screenshots");
const SIM = process.argv.includes("--simulated");
const ONLY = process.argv.find((a) => a.startsWith("--only="))?.slice(7);
const PORT = SIM ? 4174 : 4173;
const BASE = `http://localhost:${PORT}`;
const SIZES = [["1440", { width: 1440, height: 900 }], ["1024", { width: 1024, height: 768 }], ["390", { width: 390, height: 844 }]];
const THEMES = ["light", "dark"];
const content = JSON.parse(readFileSync(join(SITE, "src", "generated", "content.json"), "utf8"));

// ---- progress fixtures (the site's own export format) -------------------------------------
const now = new Date();
const iso = (d) => d.toISOString();
const today = (h, m) => { const d = new Date(now); d.setHours(h, m, 0, 0); return iso(d); };
const localDate = (d = now) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const J = (key, status, method, detail, started = null, done = null) =>
  ({ id: key, data: { step_key: key, status, method, detail, started_at: started, done_at: done } });
function lessonDone(id) {
  const L = content.lessons.find((l) => l.id === id);
  const acts = {};
  for (const s of L.steps) for (const b of s.blocks) {
    if (b.kind === "md" || !b.id) continue;
    acts[b.id] = b.kind === "python" ? { kind: "python", ok: true, at: iso(now) }
      : b.kind === "checkpoint" ? { kind: "checkpoint", passed: true, at: iso(now), hints_used: 0, solution_viewed: false }
      : { kind: "predict", answer: b.data.answer ?? 0, correct: true, at: iso(now) };
  }
  return { id, data: { lesson_id: id, status: "completed", current_step: L.steps[L.steps.length - 1].id, completed_steps: L.steps.map((s) => s.id),
    activities: acts, prereq_override: false, started_at: iso(now), completed_at: iso(now) } };
}
function lessonStarted(id, stepIndex) {
  const L = content.lessons.find((l) => l.id === id);
  return { id, data: { lesson_id: id, status: "in_progress", current_step: L.steps[stepIndex].id, completed_steps: [], activities: {},
    prereq_override: false, started_at: iso(now), completed_at: null } };
}
const cards = (ids) => content.lessons.filter((l) => ids.includes(l.id)).flatMap((l) => l.flashcards.map((c) => ({ c, l })));
function file(tables) {
  const all = ["lesson_progress", "exercise_attempts", "exercise_drafts", "notes", "flashcard_state", "review_log", "session_log", "journey_state"];
  return { app: "tsfm-reality-check", schema: 1, exported_utc: iso(now),
    tables: Object.fromEntries(all.map((t) => [t, (tables[t] ?? []).map((r) => ({ ...r, updated_at: iso(now), deleted: false }))])) };
}
const tour = J("site:welcome", "done", "site", "tour finished", null, iso(now));
const sessions = (minutes) => [{ id: "s1", data: { started_at: today(9, 0), ended_at: today(12, 0), active_seconds: minutes * 60, events: [] } }];
const due = (ids, n) => cards(ids).slice(0, n).map(({ c, l }) => ({ id: c.id, data: { card_id: c.id, lesson_id: l.id, ease: 2.5, interval_days: 1,
  repetitions: 1, lapses: 0, due: localDate(), last_reviewed: null } }));
const SETUP = J("task:setup", "done", "output", "doctor: 21 OK, 1 optional", null, iso(now));
const STATES = {
  fresh: file({ journey_state: [tour] }),
  running: file({
    journey_state: [tour, SETUP, J("task:run-study", "started", null, "", today(14, 5))],
    lesson_progress: [lessonDone("00"), lessonDone("01"), lessonDone("02")],
    flashcard_state: due(["00", "01", "02"], 4), session_log: sessions(160),
  }),
  published: file({
    journey_state: [tour, SETUP, J("task:run-study", "done", "output", "run default: 26 tickers, 3/3 models available", today(8, 0), today(13, 10))],
    lesson_progress: ["00", "01", "02", "03", "04", "05", "06", "07", "08"].map(lessonDone),
    flashcard_state: due(["00", "01", "02"], 6), session_log: sessions(11 * 60 + 25),
  }),
  done: file({
    journey_state: [tour, SETUP, J("task:run-study", "done", "output", "run default: 26 tickers, 3/3 models available", today(8, 0), today(13, 10)),
      J("site:results", "done", "site", "opened the Results page with real results", null, iso(now)), J("task:audit", "done", "output", "tests: 306 passed", null, iso(now))],
    lesson_progress: content.lessons.map((l) => lessonDone(l.id)),
    session_log: sessions(15 * 60 + 40),
  }),
  lesson02: file({ journey_state: [tour, SETUP], lesson_progress: [lessonDone("00"), lessonDone("01"), lessonStarted("02", 1)] }),
};

async function load(page, state) {
  await page.goto(`${BASE}/account`);
  await page.getByTestId("import-file").setInputFiles({ name: "p.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(STATES[state])) });
  await page.getByTestId("account-message").filter({ hasText: "Imported" }).waitFor();
}

// ---- server -------------------------------------------------------------------------------
function simulatedBuild() {
  const dist = join(SITE, "dist-simulated");
  const gen = join(SITE, "src", "generated", "status.json");
  const original = readFileSync(gen, "utf8");
  const status = JSON.parse(original);
  status.runs.push({ run: "default", synthetic: false, label: "SIMULATED for screenshots", version: "simulated", published_utc: iso(now),
    provenance: {}, model_status: {} });
  status.real_results_available = true;
  try {
    writeFileSync(gen, JSON.stringify(status));
    execFileSync("npx", ["vite", "build", "--outDir", dist, "--emptyOutDir"], { cwd: SITE, stdio: "inherit" });
  } finally {
    writeFileSync(gen, original);
  }
  return dist;
}

async function serve(outDir) {
  const p = spawn("npx", ["vite", "preview", "--port", String(PORT), "--strictPort", ...(outDir ? ["--outDir", outDir] : [])], { cwd: SITE, stdio: "ignore" });
  for (let i = 0; i < 60; i++) {
    try { if ((await fetch(BASE)).ok) return p; } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error("preview server did not start");
}

// ---- shots --------------------------------------------------------------------------------
const PREDICT = "/lessons/02?step=volatility-comes-in-clusters";
const toPredict = (page) => page.getByTestId("forecast-chart").evaluate((el) => window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 180 }));
const SHOTS = SIM ? [
  { name: "home-published-SIMULATED", state: "published", go: "/" },
  { name: "home-all-done-SIMULATED", state: "done", go: "/" },
] : [
  { name: "home-fresh", state: "fresh", go: "/" },
  { name: "home-study-running", state: "running", go: "/" },
  { name: "home-study-running-rail-open", state: "running", go: "/", sizes: ["390"], after: (p) => p.getByTestId("rail-toggle").click() },
  { name: "home-finished-dialog", state: "running", go: "/", sizes: ["1440", "390"], after: (p) => p.getByTestId("study-finished").click() },
  { name: "lesson-predict-1-before", state: "lesson02", go: PREDICT, sizes: ["1440"] },
  { name: "lesson-predict-1-before-scrolled", state: "lesson02", go: PREDICT, sizes: ["1024", "390"], after: toPredict },
  { name: "lesson-predict-2-selected", state: "lesson02", go: PREDICT,
    after: async (p) => { await p.getByRole("radio", { name: /fade slowly/ }).check(); await toPredict(p); } },
  { name: "lesson-predict-3-correct", state: "lesson02", go: PREDICT,
    after: async (p) => { await p.getByRole("radio", { name: /fade slowly/ }).check(); await p.getByTestId("predict-check").click();
      await p.waitForTimeout(700); await toPredict(p); } },
  { name: "lesson-predict-4-incorrect", state: "lesson02", go: PREDICT,
    after: async (p) => { await p.getByRole("radio", { name: /Snap back/ }).check(); await p.getByTestId("predict-check").click();
      await p.waitForTimeout(700); await toPredict(p); } },
  { name: "your-path", state: "running", go: "/path" },
  { name: "results", state: "fresh", go: "/results", after: (p) => p.getByTestId("primary-card").waitFor() },
];

mkdirSync(OUT, { recursive: true });
const server = await serve(SIM ? simulatedBuild() : null);
const browser = await chromium.launch();
try {
  for (const shot of SHOTS.filter((s) => !ONLY || s.name.includes(ONLY)))
    for (const [label, viewport] of SIZES.filter(([l]) => !shot.sizes || shot.sizes.includes(l)))
      for (const theme of THEMES) {
        const ctx = await browser.newContext({ viewport, colorScheme: theme, reducedMotion: "no-preference" });
        const page = await ctx.newPage();
        page.on("dialog", (d) => void d.accept());
        await load(page, shot.state);
        await page.goto(`${BASE}${shot.go}`);
        await page.waitForLoadState("networkidle");
        await page.evaluate(() => document.fonts.ready);
        if (shot.after) await shot.after(page);
        await page.waitForTimeout(150);
        const path = join(OUT, `${shot.name}-${label}-${theme}.png`);
        await page.screenshot({ path });
        console.log("wrote", path.replace(SITE + "/", ""));
        await ctx.close();
      }
} finally {
  await browser.close();
  server.kill();
  if (SIM && existsSync(join(SITE, "dist-simulated"))) rmSync(join(SITE, "dist-simulated"), { recursive: true });
}
