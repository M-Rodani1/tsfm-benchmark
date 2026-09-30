/// <reference lib="webworker" />
// The browser's Python: Pyodide in a Web Worker, so the page never freezes.
// Core runtime self-hosted under /pyodide/v<ver>/; scientific packages from the Pyodide CDN
// (packageBaseUrl, pinned to the same version, integrity-checked against the lock file).
import type { PyodideAPI } from "pyodide";
import helperSource from "./site_helper.py?raw";
import type { FromWorker, RunResult, ToWorker } from "./protocol";

declare const self: DedicatedWorkerGlobalScope;
const ROOT = "/home/pyodide/tsfm";
let py: PyodideAPI | null = null;
let currentId = 0;
let queue: Promise<void> = Promise.resolve();

const post = (m: FromWorker) => self.postMessage(m);
const status = (stage: "loading" | "ready" | "error", text: string) => post({ type: "status", stage, text });

async function fetchBytes(url: string): Promise<Uint8Array> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`could not load ${url} (${r.status})`);
  return new Uint8Array(await r.arrayBuffer());
}

function writeFile(path: string, bytes: Uint8Array) {
  const dir = path.slice(0, path.lastIndexOf("/"));
  py!.FS.mkdirTree(dir);
  py!.FS.writeFile(path, bytes);
}

async function init(msg: Extract<ToWorker, { type: "init" }>) {
  status("loading", "Starting Python (Pyodide)…");
  const origin = self.location.origin;
  const { loadPyodide } = (await import(/* @vite-ignore */ `${origin}${msg.indexURL}pyodide.mjs`)) as typeof import("pyodide");
  py = await loadPyodide({
    indexURL: `${origin}${msg.indexURL}`,
    packageBaseUrl: msg.packageBaseUrl,
    env: { TSFM_RC_ROOT: ROOT, MPLBACKEND: "Agg", HOME: "/home/pyodide" },
  });
  py.setStdout({ batched: (text: string) => post({ type: "stream", id: currentId, name: "stdout", text: text + "\n" }) });
  py.setStderr({ batched: (text: string) => post({ type: "stream", id: currentId, name: "stderr", text: text + "\n" }) });
  status("loading", `Loading ${msg.packages.join(", ")}… (first visit: about 40 MB, then cached)`);
  await py.loadPackage(msg.packages, { messageCallback: () => {}, errorCallback: () => {} });
  const missing = msg.packages.filter((p) => !(p in py!.loadedPackages));
  if (missing.length)
    throw new Error(`Could not download the Python packages (${missing.join(", ")}) from cdn.jsdelivr.net. ` +
      "Check your internet connection or content blockers, then press Restart Python. After one successful load they are cached.");
  status("loading", "Installing tsfm_rc…");
  const micropip = py.pyimport("micropip");
  await micropip.install.callKwargs(`${origin}${msg.wheelUrl}`, { deps: false });
  micropip.destroy();
  py.FS.mkdirTree(ROOT);
  writeFile("/home/pyodide/site_helper.py", new TextEncoder().encode(helperSource));
  await py.runPythonAsync("import sys; sys.path.insert(0, '/home/pyodide'); import site_helper; site_helper.reset()");
  status("ready", `Python ${py.version} ready`);
}

async function call(fn: string, ...args: unknown[]): Promise<RunResult> {
  const helper = py!.pyimport("site_helper");
  const proxy = await helper[fn](...args);
  const result = proxy.toJs({ dict_converter: Object.fromEntries }) as RunResult;
  proxy.destroy();
  helper.destroy();
  return result;
}

async function handle(msg: ToWorker) {
  try {
    switch (msg.type) {
      case "init":
        await init(msg);
        break;
      case "mount":
        for (const f of msg.files) writeFile(`${ROOT}/${f.path}`, await fetchBytes(`${self.location.origin}${f.url}`));
        break;
      case "lesson": {
        await py!.runPythonAsync("import site_helper; site_helper.reset()");
        for (const a of msg.assets) writeFile(`/home/pyodide/lesson/${a.name}`, await fetchBytes(`${self.location.origin}${a.url}`));
        break;
      }
      case "run":
        currentId = msg.id;
        post({ type: "result", id: msg.id, result: await call("run", msg.code, msg.filename) });
        break;
      case "check":
        currentId = msg.id;
        post({ type: "result", id: msg.id, result: await call("check", msg.code, msg.fn, msg.checker) });
        break;
    }
    if ("id" in msg) post({ type: "done", id: msg.id });
  } catch (e) {
    const text = e instanceof Error ? e.message : String(e);
    if (msg.type === "run" || msg.type === "check")
      post({ type: "result", id: msg.id, result: { ok: false, figures: [], error: { type: "RuntimeError", message: text, line: null, traceback: "" } } });
    else status("error", text.split("\n").slice(-3).join(" ").slice(0, 400));
  }
}

// one message at a time, in order (async Python must not interleave)
self.onmessage = (ev: MessageEvent<ToWorker>) => {
  queue = queue.then(() => handle(ev.data));
};
