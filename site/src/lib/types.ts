// Types of the compiled lesson bundle (src/generated/content.json, built by scripts/content.mjs).

export interface MdBlock { kind: "md"; text: string }
export interface PythonBlock { kind: "python"; id: string; text: string }
export interface PredictData {
  question: string;
  options?: string[];
  answer?: number;
  kind?: "choice" | "number" | "text";
  tolerance?: number;
  unit?: string;
  explain: string;
}
export interface PredictBlock { kind: "predict"; id: string; text: string; data: PredictData }
export interface CheckpointBlock { kind: "checkpoint"; id: string; text: string }
export type Block = MdBlock | PythonBlock | PredictBlock | CheckpointBlock;

export interface Step { id: string; title: string; blocks: Block[] }
export interface ErrorExplanation { see: string; match: string; why: string; fix: string }
export interface Flashcard { id: string; q: string; a: string }
export interface MountFile { path: string; url: string }

export interface Lesson {
  id: string;
  slug: string;
  title: string;
  minutes: number;
  objectives: string[];
  prerequisites: string[];
  youNeed: string;
  codeToRead: string[];
  browserNote: string | null;
  next: string | null;
  mounts: string[];
  mountFiles: MountFile[];
  assets: { name: string; url: string }[];
  steps: Step[];
  exercise: { function: string; hints: string[]; starter: string; solution: string; checker: string };
  flashcards: Flashcard[];
  errors: ErrorExplanation[];
}

export interface ContentBundle { lessons: Lesson[]; errors: ErrorExplanation[] }

export interface Runtime {
  pyodide: { version: string; indexURL: string; packageBaseUrl: string; packages: string[]; python: string;
    lockedVersions: Record<string, string | null>; thirdPartyImports: string[] };
  wheel: { url: string; sha256: string; version: string };
  supabaseConfigured: boolean;
}

export interface TerminalTask { id: string; title: string; why: string; minutes: string; commands: string[] }
export interface ResearchStatus {
  generated_from: { commit: string | null; docs: string[] };
  builds: { id: string; commit: string; summary: string }[];
  amendments: { id: string; date: string; when: string; title: string }[];
  audits: { id: string; title: string; items: string[] }[];
  phases: { id: string; title: string; status: "done" | "pending"; detail: string }[];
  runs: { run: string; synthetic: boolean; label: string; version: string; published_utc: string;
    provenance: Record<string, string | boolean | null>; model_status: Record<string, { status: string; reason?: string; release_date?: string }> }[];
  real_results_available: boolean;
  terminal_tasks: TerminalTask[];
}
