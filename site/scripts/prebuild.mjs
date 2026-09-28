// Everything the site needs from the repository, generated before `vite build`/`vite dev`:
//   src/generated/content.json   lessons + error explanations (from site/content)
//   src/generated/status.json    research status (from docs + published results)
//   src/generated/runtime.json   Pyodide version/packages + tsfm_rc wheel location
//   public/pyodide/v<ver>/       self-hosted Pyodide core (packages come from the CDN)
//   public/py/<hash>/*.whl       tsfm_rc wheel for micropip
//   public/data/{fixtures,configs,lessons}/  files mounted into the browser's Python
// Fails (exit 1) on any content-rule violation, unavailable package or secret key.
import { createHash } from "node:crypto";
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { buildContent } from "./content.mjs";
import { checkSupabaseEnv } from "./env.mjs";
import { checkPyodide, pyodideDir } from "./pyodide.mjs";
import { buildStatus } from "./status.mjs";
import { buildWheel } from "./wheel.mjs";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = join(SITE, "..");
const GEN = join(SITE, "src", "generated");
const PUB = join(SITE, "public");

function fail(msgs) {
  for (const m of msgs) console.error(`  ✗ ${m}`);
  process.exit(1);
}

function writeJson(p, obj) {
  mkdirSync(dirname(p), { recursive: true });
  writeFileSync(p, JSON.stringify(obj, null, 1) + "\n");
}

function resetDir(d) {
  rmSync(d, { recursive: true, force: true });
  mkdirSync(d, { recursive: true });
}

const env = checkSupabaseEnv();
if (env.problems.length) fail(env.problems);

const content = buildContent(REPO);
if (content.problems.length) fail(content.problems);
const py = checkPyodide(content.lessons);
if (py.problems.length) fail(py.problems);

// Pyodide core, self-hosted (versioned path -> immutable cache)
resetDir(join(PUB, "pyodide"));
const pyDest = join(PUB, py.indexPath);
mkdirSync(pyDest, { recursive: true });
for (const f of ["pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"])
  copyFileSync(join(pyodideDir(), f), join(pyDest, f));

// fixtures (synthetic, checked against their committed SHA-256), configs, lesson assets
resetDir(join(PUB, "data", "fixtures"));
const manifest = JSON.parse(readFileSync(join(REPO, "data", "fixtures", "MANIFEST.json"), "utf8"));
for (const [f, sha] of Object.entries(manifest.files)) {
  const buf = readFileSync(join(REPO, "data", "fixtures", f));
  if (createHash("sha256").update(buf).digest("hex") !== sha) fail([`fixture ${f} does not match MANIFEST.json`]);
  writeFileSync(join(PUB, "data", "fixtures", f), buf);
}
copyFileSync(join(REPO, "data", "fixtures", "MANIFEST.json"), join(PUB, "data", "fixtures", "MANIFEST.json"));
resetDir(join(PUB, "data", "configs"));
for (const f of readdirSync(join(REPO, "configs")).filter((n) => n.endsWith(".yaml")))
  copyFileSync(join(REPO, "configs", f), join(PUB, "data", "configs", f));
resetDir(join(PUB, "data", "lessons"));
for (const L of content.lessons)
  for (const a of L.assets) {
    mkdirSync(join(PUB, "data", "lessons", L.slug), { recursive: true });
    copyFileSync(join(REPO, "site", "content", "lessons", L.slug, a.name), join(PUB, "data", "lessons", L.slug, a.name));
  }

// tsfm_rc wheel
const wheel = buildWheel(REPO);
resetDir(join(PUB, "py"));
const wheelDir = join(PUB, "py", wheel.sha256.slice(0, 12));
mkdirSync(wheelDir, { recursive: true });
writeFileSync(join(wheelDir, wheel.filename), wheel.bytes);

if (!existsSync(join(PUB, "data", "results", "index.json"))) fail(["site/public/data/results/index.json missing: run `make publish-results`"]);
writeJson(join(GEN, "content.json"), { lessons: content.lessons, errors: content.errors });
writeJson(join(GEN, "status.json"), buildStatus(REPO));
writeJson(join(GEN, "runtime.json"), {
  pyodide: { version: py.version, indexURL: py.indexPath, packageBaseUrl: py.packageBaseUrl, packages: py.packages,
    python: py.python, lockedVersions: py.lockedVersions, thirdPartyImports: py.thirdPartyImports },
  wheel: { url: `/py/${wheel.sha256.slice(0, 12)}/${wheel.filename}`, sha256: wheel.sha256, version: wheel.version },
  supabaseConfigured: env.configured,
});
console.log(`[prebuild] ${content.lessons.length} lessons, Pyodide ${py.version} (Python ${py.python}), ` +
  `packages ${py.packages.join(", ")}; wheel ${wheel.filename} (${wheel.modules} files); ` +
  `Supabase ${env.configured ? "configured" : "not configured (local-only mode)"}`);
