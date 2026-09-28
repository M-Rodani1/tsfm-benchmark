// Page-side client of the Python worker (one per tab).
// - starts the worker lazily and reports its status to the UI;
// - mounts each lesson's files once, and resets the Python namespace when the lesson changes;
// - before running a cell, runs every earlier cell of the lesson not yet run in this session
//   (like "run all above"), so a learner can jump to any step;
// - "Restart Python" terminates the worker (the only way to stop a runaway loop).
import { pythonCells, runtime } from "../lib/content";
import type { Lesson } from "../lib/types";
import type { FromWorker, RunResult, ToWorker } from "./protocol";

export type RunnerState = { stage: "idle" | "loading" | "ready" | "busy" | "error"; text: string };
type Stream = (name: "stdout" | "stderr", text: string) => void;
type Request = { type: "run"; code: string; filename: string } | { type: "check"; code: string; fn: string; checker: string };

export class PythonRunner {
  private worker: Worker | null = null;
  private ready: Promise<void> | null = null;
  private nextId = 1;
  private waiting = new Map<number, { resolve: (r: RunResult) => void; stream?: Stream }>();
  private listeners = new Set<() => void>();
  private mounted = new Set<string>();
  private lessonSlug: string | null = null;
  private ranCells = new Set<string>();
  state: RunnerState = { stage: "idle", text: "Python starts when you run a cell." };

  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };
  getState = () => this.state;
  private setState(s: RunnerState) {
    this.state = s;
    for (const fn of this.listeners) fn();
  }

  private send(msg: ToWorker) {
    this.worker!.postMessage(msg);
  }

  start(): Promise<void> {
    if (this.ready) return this.ready;
    this.worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
    this.ready = new Promise<void>((resolve, reject) => {
      this.worker!.onmessage = (ev: MessageEvent<FromWorker>) => {
        const m = ev.data;
        if (m.type === "status") {
          this.setState({ stage: m.stage === "ready" ? "ready" : m.stage, text: m.text });
          if (m.stage === "ready") resolve();
          if (m.stage === "error") reject(new Error(m.text));
        } else if (m.type === "stream") this.waiting.get(m.id)?.stream?.(m.name, m.text);
        else if (m.type === "result") {
          const w = this.waiting.get(m.id);
          this.waiting.delete(m.id);
          w?.resolve(m.result);
        }
      };
      this.worker!.onerror = (e) => {
        this.setState({ stage: "error", text: `Python worker failed: ${e.message}` });
        reject(new Error(e.message));
      };
    });
    const p = runtime.pyodide;
    this.send({ type: "init", indexURL: p.indexURL, packageBaseUrl: p.packageBaseUrl, packages: p.packages, wheelUrl: runtime.wheel.url });
    return this.ready;
  }

  restart() {
    this.worker?.terminate();
    for (const w of this.waiting.values())
      w.resolve({ ok: false, figures: [], error: { type: "Interrupted", message: "Python was restarted.", line: null, traceback: "" } });
    this.waiting.clear();
    this.worker = null;
    this.ready = null;
    this.mounted.clear();
    this.lessonSlug = null;
    this.ranCells.clear();
    this.setState({ stage: "idle", text: "Python restarted. It starts again when you run a cell." });
  }

  private request(msg: Request, stream?: Stream): Promise<RunResult> {
    const id = this.nextId++;
    return new Promise((resolve) => {
      this.waiting.set(id, { resolve, stream });
      this.send({ ...msg, id } as ToWorker);
    });
  }

  async openLesson(lesson: Lesson) {
    await this.start();
    if (this.lessonSlug === lesson.slug) return;
    const files = lesson.mountFiles.filter((f) => !this.mounted.has(f.path));
    if (files.length) {
      this.setState({ stage: "busy", text: `Loading ${files.length} data file(s) for this lesson…` });
      this.send({ type: "mount", files });
      files.forEach((f) => this.mounted.add(f.path));
    }
    this.send({ type: "lesson", slug: lesson.slug, assets: lesson.assets });
    this.lessonSlug = lesson.slug;
    this.ranCells.clear();
    this.setState({ stage: "ready", text: this.state.text.startsWith("Python") ? this.state.text : "Python ready" });
  }

  /** Run earlier cells that have not run yet in this session. Returns the failing cell id, if any. */
  private async runEarlier(lesson: Lesson, uptoCellId: string | null, codeFor: (cellId: string) => string): Promise<{ cellId: string; result: RunResult } | null> {
    for (const cell of pythonCells(lesson)) {
      if (cell.id === uptoCellId) break;
      if (this.ranCells.has(cell.id)) continue;
      this.setState({ stage: "busy", text: `Running an earlier cell first (${cell.id.split(".")[0]})…` });
      const r = await this.request({ type: "run", code: codeFor(cell.id), filename: `<${cell.id}>` });
      if (!r.ok) return { cellId: cell.id, result: r };
      this.ranCells.add(cell.id);
    }
    return null;
  }

  private unavailable(e: unknown): RunResult {
    return { ok: false, figures: [], error: { type: "PythonUnavailable", message: e instanceof Error ? e.message : String(e), line: null, traceback: "" } };
  }

  async runCell(lesson: Lesson, cellId: string, code: string, codeFor: (cellId: string) => string, stream?: Stream): Promise<RunResult & { earlierFailed?: string }> {
    try {
      await this.openLesson(lesson);
    } catch (e) {
      return this.unavailable(e);
    }
    const earlier = await this.runEarlier(lesson, cellId, codeFor);
    if (earlier) {
      this.setState({ stage: "ready", text: "Python ready" });
      return { ...earlier.result, earlierFailed: earlier.cellId };
    }
    this.setState({ stage: "busy", text: "Running…" });
    const r = await this.request({ type: "run", code, filename: `<${cellId}>` }, stream);
    if (r.ok) this.ranCells.add(cellId);
    this.setState({ stage: "ready", text: "Python ready" });
    return r;
  }

  async check(lesson: Lesson, code: string, codeFor: (cellId: string) => string, stream?: Stream): Promise<RunResult & { earlierFailed?: string }> {
    try {
      await this.openLesson(lesson);
    } catch (e) {
      return this.unavailable(e);
    }
    const earlier = await this.runEarlier(lesson, null, codeFor);
    if (earlier) {
      this.setState({ stage: "ready", text: "Python ready" });
      return { ...earlier.result, earlierFailed: earlier.cellId };
    }
    this.setState({ stage: "busy", text: "Checking…" });
    const r = await this.request({ type: "check", code, fn: lesson.exercise.function, checker: lesson.exercise.checker }, stream);
    this.setState({ stage: "ready", text: "Python ready" });
    return r;
  }
}

export const runner = new PythonRunner();
