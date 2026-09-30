// Checks for output pasted from a terminal task. Pure functions, no DOM.
//
// Every marker below is copied from the code that prints it, not guessed:
//   make doctor            src/tsfm_rc/pipeline/doctor.py  run_doctor(): " ✓ OK    name  detail", "→ fix",
//                          and one of three summary lines
//   make fetch-data        src/tsfm_rc/cli.py  _cmd_fetch(): "<TICKER> ok …" / "<TICKER> FAILED: …",
//                          "N ticker(s) failed."
//   make reproduce         src/tsfm_rc/pipeline/run.py + cli.py: "[validate] <config>: OK", "[data] …",
//                          "[tsfm] <model>: AVAILABLE|UNAVAILABLE: …", "[report] …/reports/<run>/RESULTS.md",
//                          "[dashboard] …", "[data] no data available; stopping."
//   make publish-results   cli.py _cmd_publish(): "[publish] <run>: version <v> (<label or 'real data'>) -> …"
//   make test              pytest's summary line: "302 passed, 9 warnings in 258.32s"
//   GNU make / shells      "make: *** [Makefile:69: doctor] Error 1", "No rule to make target",
//                          "make: uv: No such file or directory", "command not found"
// Real captured outputs are in site/tests/fixtures/cli (see its README) and are used by
// site/tests/cliparse.test.ts.
import type { ErrorExplanation } from "./types";

export type Verdict = "success" | "partial" | "failure" | "unrecognised";

export interface CheckProblem { title: string; detail?: string; fix?: string }

export interface CheckResult {
  verdict: Verdict;
  /** One plain-English sentence: what the output says. */
  summary: string;
  problems: CheckProblem[];
  /** Short record stored with the step (never the pasted text itself). */
  detail: string;
}

// CRLF from Windows terminals, and ANSI colour codes (ESC [ … m) some terminals copy along
const ANSI = new RegExp(`${String.fromCharCode(27)}\\[[0-9;]*m`, "g");
const clean = (text: string) => text.replace(/\r\n?/g, "\n").replace(ANSI, "");

// ---------------------------------------------------------------- shell-level failures
/** Failures that happen before our own code runs (wrong folder, missing tools). */
export function shellProblems(text: string): CheckProblem[] {
  const t = clean(text);
  const out: CheckProblem[] = [];
  if (/No rule to make target [`'"]?[\w-]+['"]?/.test(t) || /No targets specified and no makefile found/.test(t))
    out.push({ title: "make could not find the project's Makefile", detail: "You are not in the project folder.",
      fix: "Run `cd tsfm-benchmark` (the folder `git clone` created), then run the command again." });
  if (/make: uv: (No such file or directory|command not found)/.test(t) || /(^|\n)[^\n]*(zsh|bash|sh): (command not found: uv|uv: command not found)/.test(t))
    out.push({ title: "uv is not installed (or not on your PATH)",
      fix: "Install uv (step “Install uv”), then open a new terminal or run `source $HOME/.local/bin/env`, and try again." });
  if (/(zsh|bash|sh): (command not found: make|make: command not found)/.test(t))
    out.push({ title: "make is not installed",
      fix: "macOS: `xcode-select --install`. Linux / Windows (WSL): `sudo apt install -y make`." });
  if (/(zsh|bash|sh): (command not found: git|git: command not found)/.test(t))
    out.push({ title: "git is not installed", fix: "macOS: `xcode-select --install`. Linux / Windows (WSL): `sudo apt install -y git`." });
  return out;
}

/** The last Python exception in a traceback, explained with site/content/errors.yaml when possible. */
export function pythonError(text: string, explanations: ErrorExplanation[]): CheckProblem | null {
  const t = clean(text);
  if (!t.includes("Traceback (most recent call last):")) return null;
  const tail = t.slice(t.lastIndexOf("Traceback (most recent call last):")).split("\n").map((l) => l.trim()).filter(Boolean);
  const last = [...tail].reverse().find((l) => /^[A-Za-z_][\w.]*(Error|Exception|Interrupt|Exit)\b/.test(l)) ?? tail[tail.length - 1];
  const hit = explanations.find((e) => {
    try {
      return new RegExp(e.match).test(last);
    } catch {
      return false;
    }
  });
  return { title: `Python stopped with an error: ${last.slice(0, 200)}`, detail: hit?.why, fix: hit?.fix };
}

function makeFailed(text: string): string | null {
  const m = clean(text).match(/make: \*\*\* \[[^\]]*?(?::\s*([\w-]+))?\] Error (\d+)/);
  return m ? `make stopped with Error ${m[2]}${m[1] ? ` (target ${m[1]})` : ""}` : null;
}

// ---------------------------------------------------------------- make doctor
export interface DoctorCheck { status: "OK" | "WARN" | "FAIL"; name: string; detail: string; fix?: string }
export interface DoctorOutput {
  checks: DoctorCheck[];
  summary: "all-passed" | "warnings-only" | "problems" | null;
  online: boolean | null;
}

/** Parse `make doctor` / `tsfm-rc doctor` output. Lines: " ✓ OK    <name padded>  <detail>", then "→ fix". */
export function parseDoctor(text: string): DoctorOutput {
  const lines = clean(text).split("\n");
  const checks: DoctorCheck[] = [];
  for (const line of lines) {
    const m = line.match(/^\s*(?:✓|!|✗)?\s*(OK|WARN|FAIL)\s{2,}(\S.*?)(?:\s{2,}(.*))?$/);
    if (m) {
      checks.push({ status: m[1] as DoctorCheck["status"], name: m[2].trim(), detail: (m[3] ?? "").trim() });
      continue;
    }
    const f = line.match(/^\s+→\s+(.*)$/);
    if (f && checks.length) checks[checks.length - 1].fix = f[1].trim();
  }
  const t = clean(text);
  const summary = /\n?All checks passed\./.test(t) ? "all-passed"
    : /Everything needed for tests, lessons and `make smoke` works\./.test(t) ? "warnings-only"
      : /\d+ problem\(s\) to fix \(✗\)/.test(t) ? "problems" : null;
  const echo = t.match(/uv run tsfm-rc doctor([^\n]*)/);
  const online = echo ? /--online/.test(echo[1]) : null;
  return { checks, summary, online };
}

/** Checks whose WARN is expected at the end of Phase 1 (they are filled in later, or optional). */
export const DOCTOR_WARN_OK = [/^real-data cache$/, /^results$/, /^lessons$/, /^uv$/];

/** Phase 1 is done when the doctor ran to the end with no ✗ and nothing the real study needs missing. */
export function checkSetup(text: string, explanations: ErrorExplanation[] = []): CheckResult {
  const shell = shellProblems(text);
  const d = parseDoctor(text);
  if (!d.checks.length || !d.summary) {
    const py = pythonError(text, explanations);
    const problems = [...shell, ...(py ? [py] : [])];
    const mk = makeFailed(text);
    if (problems.length || mk)
      return { verdict: "failure", summary: "The doctor did not run to the end.", problems: problems.length ? problems : [{ title: mk! }],
        detail: "doctor did not finish" };
    return { verdict: "unrecognised", summary: "This does not look like the output of `make doctor ONLINE=1`.", problems: [],
      detail: "unrecognised output" };
  }
  const fails = d.checks.filter((c) => c.status === "FAIL");
  const blockingWarns = d.checks.filter((c) => c.status === "WARN" && !DOCTOR_WARN_OK.some((re) => re.test(c.name)));
  const problems: CheckProblem[] = [...fails, ...blockingWarns].map((c) => ({ title: `${c.status === "FAIL" ? "✗" : "!"} ${c.name}`, detail: c.detail, fix: c.fix }));
  const counts = `${d.checks.length} checks: ${d.checks.filter((c) => c.status === "OK").length} ✓, ` +
    `${d.checks.filter((c) => c.status === "WARN").length} !, ${fails.length} ✗`;
  if (fails.length)
    return { verdict: "failure", summary: `The doctor found ${fails.length} problem(s) (✗). Fix them with the → lines below, then run it again.`,
      problems, detail: counts };
  if (blockingWarns.length) {
    const weightsOnly = blockingWarns.every((c) => c.name.startsWith("weights "));
    return { verdict: "failure",
      summary: weightsOnly && d.online === false
        ? "Everything is installed, but the model weights are not downloaded yet: run `make doctor ONLINE=1` (with ONLINE=1)."
        : "The basics work, but something the real study needs is missing (the ! lines below).",
      problems, detail: counts };
  }
  return { verdict: "success", summary: "Your laptop is ready: no ✗, and the models and packages the real study needs are in place.",
    problems: [], detail: counts };
}

// ---------------------------------------------------------------- make fetch-data / make reproduce
export interface PipelineOutput {
  config: string | null;
  run: string | null;
  provider: string | null;
  tickersLoaded: number | null;
  tickersUnavailable: number | null;
  noData: boolean;
  models: { name: string; available: boolean; reason?: string }[];
  evaluated: boolean;
  reported: boolean;
  dashboard: boolean;
}

export function parsePipeline(text: string): PipelineOutput {
  const t = clean(text);
  const config = t.match(/\[validate\] (\S+): OK/)?.[1] ?? null;
  const report = t.match(/\[report\] (\S+?)[\\/]reports[\\/]([\w.-]+)[\\/]RESULTS\.md/);
  const data = t.match(/\[data\] (\d+) tickers loaded from (\w+); (\d+) unavailable/);
  const models = [...t.matchAll(/^\[tsfm\] ([\w.-]+): (AVAILABLE|UNAVAILABLE)(?::\s*(.*))?$/gm)].map((m) => ({
    name: m[1], available: m[2] === "AVAILABLE", reason: m[3]?.trim(),
  }));
  const configRun = config?.match(/([\w.-]+)\.ya?ml$/)?.[1] ?? null;
  return {
    config,
    run: report?.[2] ?? configRun,
    provider: data?.[2] ?? null,
    tickersLoaded: data ? Number(data[1]) : null,
    tickersUnavailable: data ? Number(data[3]) : null,
    noData: /\[data\] no data available; stopping\./.test(t),
    models,
    evaluated: /\[evaluate\] \d+ tables ->/.test(t),
    reported: !!report,
    dashboard: /\[dashboard\] .*open it in any browser/.test(t),
  };
}

export interface FetchOutput { ok: string[]; failed: { ticker: string; reason: string }[]; summaryFailed: number | null }

export function parseFetch(text: string): FetchOutput {
  const t = clean(text);
  const ok = [...t.matchAll(/^([A-Z][A-Z0-9.^=-]{0,9})\s+ok \d{4}-\d\d-\d\d\.\.\d{4}-\d\d-\d\d/gm)].map((m) => m[1]);
  const failed = [...t.matchAll(/^([A-Z][A-Z0-9.^=-]{0,9})\s+FAILED: (.*)$/gm)].map((m) => ({ ticker: m[1], reason: m[2].trim() }));
  const s = t.match(/^(\d+) ticker\(s\) failed\./m);
  return { ok, failed, summaryFailed: s ? Number(s[1]) : null };
}

/** Phase 2: `make reproduce` finished for the pre-registered study (run `default`). */
export function checkStudy(text: string, explanations: ErrorExplanation[] = []): CheckResult {
  const shell = shellProblems(text);
  const p = parsePipeline(text);
  const f = parseFetch(text);
  const py = pythonError(text, explanations);
  if (p.dashboard && p.reported && p.evaluated) {
    if (p.run !== "default")
      return { verdict: "failure", summary: `This is a finished run of \`${p.run}\`, not of the real study. Phase 2 needs \`make reproduce\` (run \`default\`).`,
        problems: [], detail: `run ${p.run}` };
    const missing = p.models.filter((m) => !m.available);
    const detail = `run default: ${p.tickersLoaded ?? "?"} tickers, ${p.models.length - missing.length}/${p.models.length} models available`;
    if (missing.length)
      return { verdict: "success",
        summary: `The study finished. ${missing.length} foundation model(s) were UNAVAILABLE, so part of the primary question is unanswered: run \`make doctor ONLINE=1\`, fix what it reports, and run \`make reproduce\` again (finished work is cached).`,
        problems: missing.map((m) => ({ title: `${m.name} UNAVAILABLE`, detail: m.reason })), detail };
    return { verdict: "success", summary: "The real study finished: statistics, report and dashboard of the `default` run are on your laptop.", problems: [], detail };
  }
  if (p.noData || (f.summaryFailed !== null && f.summaryFailed > 0)) {
    const all = f.summaryFailed !== null && f.ok.length === 0;
    return { verdict: "failure",
      summary: p.noData ? "No market data could be loaded, so the study stopped." : `${f.summaryFailed} ticker(s) failed to download${all ? " (all of them)" : ""}.`,
      problems: [{ title: "Market data download failed", detail: (f.failed[0]?.reason ?? "").slice(0, 200) || undefined,
        fix: "If every ticker failed you are offline or Yahoo is blocking requests: try again later. Otherwise re-run `make fetch-data CONFIG=configs/default.yaml` (downloaded tickers are cached). Last resort: Yahoo-format CSVs with `provider: csv` (docs/DECISIONS.md, D-022)." }],
      detail: p.noData ? "no data" : `fetch: ${f.summaryFailed} failed` };
  }
  if (f.ok.length && f.summaryFailed === null && !p.config)
    return { verdict: "partial", summary: `Market data downloaded for ${f.ok.length} ticker(s). Now start the study: \`make reproduce\`.`, problems: [],
      detail: `fetch: ${f.ok.length} ok` };
  const problems = [...shell, ...(py ? [py] : [])];
  const mk = makeFailed(text);
  if (problems.length || mk)
    return { verdict: "failure", summary: "The study stopped before it finished.", problems: problems.length ? problems : [{ title: mk! }], detail: "stopped" };
  if (p.config)
    return { verdict: "partial", summary: `The run of \`${p.run}\` has started but this output does not reach the end (no \`[dashboard]\` line). Paste the output once it has finished.`,
      problems: [], detail: `run ${p.run}: not finished` };
  return { verdict: "unrecognised", summary: "This does not look like the output of `make reproduce` (or `make fetch-data`).", problems: [], detail: "unrecognised output" };
}

// ---------------------------------------------------------------- make publish-results
export interface PublishOutput { runs: { run: string; version: string; real: boolean }[]; noRealRun: boolean }

export function parsePublish(text: string): PublishOutput {
  const t = clean(text);
  const runs = [...t.matchAll(/^\[publish\] ([\w.-]+): version ([0-9a-f]+) \((.*?)\) ->/gm)].map((m) => ({
    run: m[1], version: m[2], real: m[3] === "real data",
  }));
  return { runs, noRealRun: /\[publish\] no real-data run published yet/.test(t) };
}

/** Phase 5 finishes on this site by itself once real results are published and the site has
 * rebuilt; the pasted output of `make publish-results` can only say whether the export worked. */
export function checkPublish(text: string, explanations: ErrorExplanation[] = []): CheckResult {
  const p = parsePublish(text);
  if (p.runs.length) {
    const real = p.runs.find((r) => r.real && r.run === "default");
    if (real)
      return { verdict: "partial",
        summary: `The real study was exported (version ${real.version}). Now commit and push it (commands 2–4); this step completes by itself when the site has rebuilt.`,
        problems: [], detail: `exported default ${real.version}` };
    return { verdict: "failure", summary: "Only synthetic runs were exported: the real study (`default`) has no stored results yet. Finish Phase 2 first.",
      problems: [], detail: "no real run exported" };
  }
  const problems = [...shellProblems(text), ...([pythonError(text, explanations)].filter(Boolean) as CheckProblem[])];
  if (problems.length || makeFailed(text))
    return { verdict: "failure", summary: "`make publish-results` did not finish.", problems: problems.length ? problems : [{ title: makeFailed(text)! }], detail: "failed" };
  return { verdict: "unrecognised", summary: "This does not look like the output of `make publish-results`.", problems: [], detail: "unrecognised output" };
}

// ---------------------------------------------------------------- make test
export interface PytestOutput { passed: number; failed: number; errors: number; skipped: number; failedTests: string[]; found: boolean }

export function parsePytest(text: string): PytestOutput {
  const t = clean(text);
  // the final summary, e.g. "302 passed, 9 warnings in 258.32s (0:04:18)" or "= 1 failed, 95 passed in 48.07s ="
  const lines = t.split("\n").filter((l) => /\b(passed|failed|error|errors|no tests ran)\b.* in [\d.]+s\b/.test(l));
  const last = lines[lines.length - 1] ?? "";
  const n = (word: string) => Number(last.match(new RegExp(`(\\d+) ${word}\\b`))?.[1] ?? 0);
  return {
    passed: n("passed"), failed: n("failed"), errors: n("errors") + n("error"), skipped: n("skipped"),
    failedTests: [...t.matchAll(/^(?:FAILED|ERROR) (\S+)/gm)].map((m) => m[1]),
    found: !!last,
  };
}

export function checkTests(text: string, explanations: ErrorExplanation[] = []): CheckResult {
  const p = parsePytest(text);
  if (p.found) {
    const detail = `${p.passed} passed, ${p.failed} failed, ${p.errors} errors, ${p.skipped} skipped`;
    if (p.failed || p.errors || !p.passed)
      return { verdict: "failure", summary: `The test suite is not green: ${detail}.`,
        problems: p.failedTests.slice(0, 10).map((x) => ({ title: x })), detail };
    return { verdict: "success", summary: `The full test suite passes on your laptop (${p.passed} tests).`, problems: [], detail };
  }
  const problems = [...shellProblems(text), ...([pythonError(text, explanations)].filter(Boolean) as CheckProblem[])];
  if (problems.length) return { verdict: "failure", summary: "`make test` did not run.", problems, detail: "did not run" };
  return { verdict: "unrecognised", summary: "This does not look like the output of `make test` (pytest's summary line is missing).", problems: [], detail: "unrecognised output" };
}

export const CHECKERS = { doctor: checkSetup, study: checkStudy, publish: checkPublish, tests: checkTests } as const;
export type CheckerId = keyof typeof CHECKERS;
