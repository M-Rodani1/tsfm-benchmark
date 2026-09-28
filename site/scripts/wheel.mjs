// Build a pure-Python wheel of tsfm_rc from ../src for the browser (installed with micropip).
// The wheel declares no dependencies: the site loads exactly the Pyodide packages it checked
// (scripts/pyodide.mjs), and heavy optional imports inside tsfm_rc are lazy.
import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { zipSync } from "fflate";

const MTIME = new Date("2026-01-01T00:00:00Z"); // fixed, so the wheel is byte-reproducible

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir).sort()) {
    const p = join(dir, name);
    if (name === "__pycache__") continue;
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (name.endsWith(".py")) out.push(p);
  }
  return out;
}

const b64sha = (buf) => createHash("sha256").update(buf).digest("base64url");

export function buildWheel(repo) {
  const pyproject = readFileSync(join(repo, "pyproject.toml"), "utf8");
  const version = pyproject.match(/^version\s*=\s*"([^"]+)"/m)[1];
  const dist = "tsfm_reality_check";
  const info = `${dist}-${version}.dist-info`;
  const files = {};
  for (const p of walk(join(repo, "src", "tsfm_rc"))) {
    files[relative(join(repo, "src"), p).split(sep).join("/")] = readFileSync(p);
  }
  files[`${info}/METADATA`] = Buffer.from(
    `Metadata-Version: 2.1\nName: tsfm-reality-check\nVersion: ${version}\n` +
      "Summary: TSFM Reality Check (browser build for the lesson website; no dependencies declared)\n",
  );
  files[`${info}/WHEEL`] = Buffer.from("Wheel-Version: 1.0\nGenerator: tsfm-rc-site\nRoot-Is-Purelib: true\nTag: py3-none-any\n");
  const record = Object.entries(files).map(([name, buf]) => `${name},sha256=${b64sha(buf)},${buf.length}`);
  record.push(`${info}/RECORD,,`);
  files[`${info}/RECORD`] = Buffer.from(record.join("\n") + "\n");
  const entries = {};
  for (const [name, buf] of Object.entries(files)) entries[name] = [new Uint8Array(buf), { mtime: MTIME }];
  const wheel = Buffer.from(zipSync(entries, { level: 9 }));
  const sha = createHash("sha256").update(wheel).digest("hex");
  return { filename: `${dist}-${version}-py3-none-any.whl`, bytes: wheel, sha256: sha, version, modules: Object.keys(files).length };
}
