// Research-status data for the site, generated at build time from the repository's own docs:
// docs/BUILD-REPORT.md (builds, audit corrections), docs/PREREGISTRATION.md (amendments) and
// the published results index (model status, whether real results exist).
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

export const TERMINAL_TASK_REAL_RESULTS = {
  id: "reproduce",
  title: "Run the real study on your computer",
  why:
    "No result on real market data exists yet. The benchmark and the foundation models are too heavy for a " +
    "browser: run them on a normal internet connection, publish the stored numbers, and push.",
  minutes: "1–2 h, mostly unattended",
  commands: [
    "make install-all",
    "make doctor ONLINE=1",
    "make fetch-data CONFIG=configs/default.yaml",
    "make reproduce",
    "make publish-results",
    'git add site/public/data/results && git commit -m "Publish real results" && git push',
  ],
};

function section(md, headingRe) {
  const lines = md.split("\n");
  const start = lines.findIndex((l) => headingRe.test(l));
  if (start < 0) return [];
  const level = lines[start].match(/^#+/)[0].length;
  const out = [];
  for (let i = start + 1; i < lines.length; i++) {
    const m = lines[i].match(/^(#+)\s/);
    if (m && m[1].length <= level) break;
    out.push(lines[i]);
  }
  return out;
}

const strip = (s) => s.replace(/`/g, "").replace(/\*\*/g, "").trim();

/** Build table of BUILD-REPORT §1: | Build | Commit | Contents | */
export function parseBuilds(report) {
  const rows = [];
  for (const line of section(report, /^## 1\. /)) {
    const m = line.match(/^\|\s*(\d\d)\s*\|\s*([^|]+)\|\s*(.+)\|\s*$/);
    if (m) rows.push({ id: m[1], commit: strip(m[2]), summary: strip(m[3]) });
  }
  return rows;
}

/** Amendments: "### A4 — 2026-09-28 (Audit-01): title" */
export function parseAmendments(prereg) {
  const out = [];
  for (const line of prereg.split("\n")) {
    const m = line.match(/^### (A\d+)\s+[—-]\s+(\d{4}-\d\d-\d\d)\s+\(([^)]*)\):\s*(.+)$/);
    if (m) out.push({ id: m[1], date: m[2], when: m[3], title: m[4].trim() });
  }
  return out;
}

/** Audit sections: "## 10. Audit-01 corrections" with "### ..." subsections. */
export function parseAudits(report) {
  const audits = [];
  const re = /^## \d+\.\s+(Audit-\d+)[^\n]*$/gm;
  let m;
  while ((m = re.exec(report))) {
    const body = section(report, new RegExp(`^## \\d+\\.\\s+${m[1]}`));
    const items = body.filter((l) => l.startsWith("### ")).map((l) => strip(l.slice(4)));
    audits.push({ id: m[1], title: strip(m[0].replace(/^## \d+\.\s+/, "")), items });
  }
  return audits;
}

export function researchPhases(index) {
  const runs = index.runs ?? [];
  const real = runs.filter((r) => !r.synthetic);
  const allAvail = (r) => Object.values(r.model_status ?? {}).length > 0 && Object.values(r.model_status).every((s) => s.status === "AVAILABLE");
  const phase = (id, title, done, detail) => ({ id, title, status: done ? "done" : "pending", detail });
  return [
    phase("design", "Design pre-registered (PREREGISTRATION.md, amendments dated)", true, "Fixed before any real-data or model result."),
    phase("pipeline", "Pipeline built and verified on synthetic fixtures", runs.some((r) => r.synthetic),
      "Every stage runs end to end on committed fixtures; results match the data-generating processes."),
    phase("real-data", "Real market data downloaded, baselines evaluated", real.length > 0,
      real.length ? `Published run(s): ${real.map((r) => r.run).join(", ")}` : "Needs `make reproduce` on a normal connection."),
    phase("tsfms", "Foundation models evaluated (weights loaded, forecasts cached)", real.some(allAvail),
      real.length ? "See model status below." : "Blocked until the real study runs."),
    phase("primary", "Primary results: 27 pre-registered tests", real.some(allAvail),
      "Reported whatever they say, with Holm correction."),
    phase("paper", "Write-up (lesson 10 template)", false, "After the primary results exist."),
  ];
}

export function buildStatus(repo, env = process.env) {
  const report = readFileSync(join(repo, "docs", "BUILD-REPORT.md"), "utf8");
  const prereg = readFileSync(join(repo, "docs", "PREREGISTRATION.md"), "utf8");
  const idxPath = join(repo, "site", "public", "data", "results", "index.json");
  const index = existsSync(idxPath) ? JSON.parse(readFileSync(idxPath, "utf8")) : { runs: [], real_results_available: false };
  const tasks = [];
  if (!index.real_results_available) tasks.push(TERMINAL_TASK_REAL_RESULTS);
  else {
    const latest = index.runs.find((r) => !r.synthetic);
    const missing = Object.entries(latest.model_status ?? {}).filter(([, s]) => s.status !== "AVAILABLE").map(([m]) => m);
    if (missing.length)
      tasks.push({
        id: "models",
        title: `Make the foundation models available: ${missing.join(", ")}`,
        why: "The real run has UNAVAILABLE models, so part of the primary question is unanswered.",
        minutes: "30–60 min",
        commands: ["make install-tsfm", "make doctor ONLINE=1", "make reproduce", "make publish-results", "git add site/public/data/results && git commit -m \"Publish results\" && git push"],
      });
  }
  return {
    generated_from: { commit: env.COMMIT_REF || null, docs: ["docs/BUILD-REPORT.md", "docs/PREREGISTRATION.md", "site/public/data/results/index.json"] },
    builds: parseBuilds(report),
    amendments: parseAmendments(prereg),
    audits: parseAudits(report),
    phases: researchPhases(index),
    runs: (index.runs ?? []).map((r) => ({ run: r.run, synthetic: r.synthetic, label: r.label, version: r.version,
      published_utc: r.published_utc, provenance: r.provenance, model_status: r.model_status })),
    real_results_available: !!index.real_results_available,
    terminal_tasks: tasks,
  };
}
