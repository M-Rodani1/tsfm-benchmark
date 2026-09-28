// Messages between the page and the Python worker.
import type { MountFile } from "../lib/types";

export type ToWorker =
  | { type: "init"; indexURL: string; packageBaseUrl: string; packages: string[]; wheelUrl: string }
  | { type: "mount"; files: MountFile[] }
  | { type: "lesson"; slug: string; assets: { name: string; url: string }[] }
  | { type: "run"; id: number; code: string; filename: string }
  | { type: "check"; id: number; code: string; fn: string; checker: string };

export interface PyErrorInfo { type: string; message: string; line: number | null; traceback: string }

export interface RunResult {
  ok: boolean;
  value?: string | null;
  figures: string[];
  error?: PyErrorInfo;
  passed?: boolean;
  output?: string;
}

export type FromWorker =
  | { type: "status"; stage: "loading" | "ready" | "error"; text: string }
  | { type: "stream"; id: number; name: "stdout" | "stderr"; text: string }
  | { type: "result"; id: number; result: RunResult }
  | { type: "done"; id: number };
