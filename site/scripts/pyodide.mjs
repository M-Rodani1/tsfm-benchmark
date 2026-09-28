// Build-time check of what Python can do in the browser.
// 1. Every package the site loads must be in the installed Pyodide's lock file.
// 2. Every module imported by lesson code, starters, solutions and checkers must be either in
//    Pyodide's standard library (read from python_stdlib.zip), provided by a locked package,
//    or tsfm_rc / checker. A lesson that needs e.g. `arch` fails the build.
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { unzipSync } from "fflate";

export const BASE_PACKAGES = ["micropip", "numpy", "pandas", "scipy", "matplotlib", "pydantic", "pyyaml"];
const OWN_MODULES = new Set(["tsfm_rc", "checker"]);

export function pyodideDir() {
  const require = createRequire(import.meta.url);
  return dirname(require.resolve("pyodide/package.json"));
}

export function stdlibModules(dir) {
  const zip = unzipSync(new Uint8Array(readFileSync(join(dir, "python_stdlib.zip"))), { filter: () => true });
  const names = new Set();
  for (const f of Object.keys(zip)) {
    const top = f.split("/")[0].replace(/\.py$/, "");
    if (top && !top.includes(".")) names.add(top);
  }
  for (const b of ["sys", "builtins", "math", "time", "itertools", "_io", "marshal", "gc", "errno", "posix", "_thread", "array", "select", "binascii", "zlib", "_json", "_random", "_sha2", "_struct", "_datetime", "_statistics", "_bisect", "_heapq", "_csv", "unicodedata", "cmath", "_decimal", "pyodide", "js"])
    names.add(b);
  return names;
}

export function importsOf(code) {
  const mods = new Set();
  for (const line of code.split("\n")) {
    let m = line.match(/^\s*import\s+([A-Za-z_][\w.]*(\s*,\s*[A-Za-z_][\w.]*)*)/);
    if (m) for (const part of m[1].split(",")) mods.add(part.trim().split(/\s+/)[0].split(".")[0]);
    m = line.match(/^\s*from\s+([A-Za-z_][\w.]*)\s+import\s/);
    if (m) mods.add(m[1].split(".")[0]);
  }
  return mods;
}

export function checkPyodide(lessons) {
  const dir = pyodideDir();
  const lock = JSON.parse(readFileSync(join(dir, "pyodide-lock.json"), "utf8"));
  const version = JSON.parse(readFileSync(join(dir, "package.json"), "utf8")).version;
  const problems = [];
  for (const p of BASE_PACKAGES) if (!lock.packages[p]) problems.push(`Pyodide ${version} has no package '${p}'`);
  const provided = new Set();
  for (const pkg of Object.values(lock.packages)) for (const imp of pkg.imports ?? []) provided.add(imp);
  const stdlib = stdlibModules(dir);
  const used = new Map();
  for (const L of lessons) {
    const codes = [...L.steps.flatMap((s) => s.blocks.filter((b) => b.kind === "python").map((b) => b.text)),
      L.exercise.starter, L.exercise.solution, L.exercise.checker];
    for (const code of codes)
      for (const mod of importsOf(code)) {
        if (OWN_MODULES.has(mod) || stdlib.has(mod)) continue;
        if (!provided.has(mod)) problems.push(`${L.slug}: imports '${mod}', which Pyodide ${version} does not provide`);
        else used.set(mod, (used.get(mod) ?? 0) + 1);
      }
  }
  return {
    version,
    packages: BASE_PACKAGES,
    packageBaseUrl: `https://cdn.jsdelivr.net/pyodide/v${version}/full/`,
    indexPath: `/pyodide/v${version}/`,
    python: lock.info?.python,
    thirdPartyImports: [...used.keys()].sort(),
    lockedVersions: Object.fromEntries(BASE_PACKAGES.map((p) => [p, lock.packages[p]?.version ?? null])),
    problems,
  };
}
