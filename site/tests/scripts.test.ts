// Build-time scripts: content compiler, research-status generator, security headers,
// secret-key guard, tsfm_rc wheel and the Pyodide import check.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { unzipSync } from "fflate";
import { describe, expect, it } from "vitest";
import { netlifyHeaders } from "../vite.config";
// @ts-expect-error plain ESM build scripts
import { buildContent, parseBody, words } from "../scripts/content.mjs";
// @ts-expect-error plain ESM build scripts
import { checkSupabaseEnv } from "../scripts/env.mjs";
// @ts-expect-error plain ESM build scripts
import { checkPyodide, importsOf } from "../scripts/pyodide.mjs";
// @ts-expect-error plain ESM build scripts
import { buildStatus, parseAmendments, parseBuilds } from "../scripts/status.mjs";
// @ts-expect-error plain ESM build scripts
import { buildWheel } from "../scripts/wheel.mjs";

const REPO = join(__dirname, "..", "..");

describe("content compiler", () => {
  it("parses steps and activity blocks and counts words like the Python parser", () => {
    const { steps } = parseBody("## One\nSome `code x` words.\n\n```python\nprint(1)\n```\n\n## Two\n```predict\nquestion: q\nexplain: e\n```\n");
    expect(steps.map((s: { title: string }) => s.title)).toEqual(["One", "Two"]);
    expect(steps[0].blocks.map((b: { kind: string }) => b.kind)).toEqual(["md", "python"]);
    expect(words("Some `code x` words.")).toBe(3);
  });
  it("builds all lessons without rule violations", () => {
    const c = buildContent(REPO);
    expect(c.problems).toEqual([]);
    expect(c.lessons.length).toBeGreaterThanOrEqual(10);
    for (const l of c.lessons) {
      expect(l.flashcards.length).toBeGreaterThanOrEqual(5);
      expect(l.exercise.hints.length).toBeGreaterThanOrEqual(2);
      expect(l.mountFiles.every((f: { url: string }) => f.url.startsWith("/data/"))).toBe(true);
    }
  });
});

describe("research status", () => {
  it("reads builds and dated amendments from the docs and asks for the real run while none exists", () => {
    const s = buildStatus(REPO, {});
    expect(s.builds.map((b: { id: string }) => b.id)).toEqual(expect.arrayContaining(["01", "08"]));
    expect(s.amendments.map((a: { id: string }) => a.id)).toEqual(expect.arrayContaining(["A1", "A2", "A3", "A4"]));
    expect(s.real_results_available).toBe(false);
    expect(s.terminal_tasks[0].commands).toContain("make reproduce");
    expect(s.terminal_tasks[0].commands).toContain("make publish-results");
    expect(parseBuilds("## 1. X\n| 02 | `abc` | text |\n## 2. Y")).toEqual([{ id: "02", commit: "abc", summary: "text" }]);
    expect(parseAmendments("### A9 — 2027-01-01 (Audit-02): something")[0]).toEqual({ id: "A9", date: "2027-01-01", when: "Audit-02", title: "something" });
  });
});

describe("security", () => {
  it("serves strict headers (also used by `vite preview` in the browser tests)", () => {
    const h = netlifyHeaders();
    const csp = h["Content-Security-Policy"];
    expect(csp).toMatch(/default-src 'self'/);
    expect(csp).toMatch(/script-src 'self' 'wasm-unsafe-eval'(;|$)/); // no 'unsafe-eval', no remote scripts
    expect(csp).toMatch(/frame-ancestors 'none'/);
    expect(h["X-Content-Type-Options"]).toBe("nosniff");
    expect(h["Strict-Transport-Security"]).toMatch(/max-age=/);
  });
  it("refuses a service-role or secret key in the build environment", () => {
    const jwt = (role: string) => ["x", Buffer.from(JSON.stringify({ role })).toString("base64url"), "y"].join(".");
    expect(checkSupabaseEnv({ VITE_SUPABASE_URL: "https://a.supabase.co", VITE_SUPABASE_ANON_KEY: jwt("anon") }).problems).toEqual([]);
    expect(checkSupabaseEnv({ VITE_SUPABASE_URL: "u", VITE_SUPABASE_ANON_KEY: jwt("service_role") }).problems.length).toBe(1);
    expect(checkSupabaseEnv({ VITE_SUPABASE_URL: "u", VITE_SUPABASE_ANON_KEY: "sb_secret_abc" }).problems.length).toBe(1);
    expect(checkSupabaseEnv({}).configured).toBe(false);
  });
  it("no secret key is committed in the site", () => {
    for (const f of ["../.env.example", "../../netlify.toml", "../src/lib/supabase.ts"]) {
      const text = readFileSync(join(__dirname, f), "utf8");
      expect(text).not.toMatch(/sb_secret_[A-Za-z0-9]/);
      expect(text).not.toMatch(/eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/);
    }
  });
});

describe("browser Python", () => {
  it("builds a reproducible pure-Python wheel of tsfm_rc with a valid RECORD", () => {
    const a = buildWheel(REPO);
    const b = buildWheel(REPO);
    expect(a.sha256).toBe(b.sha256);
    expect(a.filename).toMatch(/^tsfm_reality_check-.+-py3-none-any\.whl$/);
    const files = unzipSync(new Uint8Array(a.bytes));
    expect(Object.keys(files)).toEqual(expect.arrayContaining(["tsfm_rc/__init__.py", "tsfm_rc/learn.py", "tsfm_rc/models/garch_np.py"]));
    const record = new TextDecoder().decode(Object.entries(files).find(([n]) => n.endsWith("/RECORD"))![1]);
    expect(record).toMatch(/tsfm_rc\/eval\/dm\.py,sha256=/);
    const meta = new TextDecoder().decode(Object.entries(files).find(([n]) => n.endsWith("/METADATA"))![1]);
    expect(meta).not.toMatch(/Requires-Dist/); // the site loads exactly the checked Pyodide packages
  });
  it("finds imports and rejects a lesson importing a package Pyodide lacks", () => {
    expect([...importsOf("import numpy as np\nfrom arch import arch_model\nimport os, sys\n")].sort()).toEqual(["arch", "numpy", "os", "sys"]);
    const fake = [{ slug: "99-x", steps: [{ blocks: [{ kind: "python", text: "from arch import arch_model" }] }],
      exercise: { starter: "", solution: "", checker: "" } }];
    const res = checkPyodide(fake);
    expect(res.problems.join()).toMatch(/imports 'arch'/);
    const ok = checkPyodide(buildContent(REPO).lessons);
    expect(ok.problems).toEqual([]);
    expect(ok.packages).toEqual(expect.arrayContaining(["numpy", "pandas", "scipy", "matplotlib"]));
  });
});

describe("parser parity (JavaScript site build vs Python notebook generator)", () => {
  it("every lesson has the same steps and the same code cells in both", () => {
    const { lessons } = buildContent(REPO);
    for (const l of lessons) {
      const nb = JSON.parse(readFileSync(join(REPO, "lessons", l.slug, "lesson.ipynb"), "utf8")) as {
        cells: { cell_type: string; source: string | string[]; metadata: { tags?: string[] } }[];
      };
      const src = (c: { source: string | string[] }) => (Array.isArray(c.source) ? c.source.join("") : c.source);
      const code = nb.cells.filter((c) => c.cell_type === "code" && !(c.metadata.tags ?? []).length).map(src);
      const jsCode = l.steps.flatMap((s: { blocks: { kind: string; text: string }[] }) => s.blocks.filter((b) => b.kind === "python").map((b) => b.text));
      expect(code, l.slug).toEqual(jsCode);
      const headings = nb.cells.filter((c) => c.cell_type === "markdown").map(src).filter((t) => t.startsWith("## ") && !t.startsWith("## Flashcards"))
        .map((t) => t.split("\n")[0].slice(3));
      expect(headings, l.slug).toEqual(l.steps.map((s: { title: string }) => s.title));
      const exercise = nb.cells.find((c) => (c.metadata.tags ?? []).includes("exercise"))!;
      expect(src(exercise), l.slug).toBe(l.exercise.starter);
    }
  });
});
