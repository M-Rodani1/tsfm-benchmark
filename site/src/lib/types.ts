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
  /** A chart question: figures/<figure>.json of the lesson, loaded at build time. */
  figure?: string;
  figureData?: ForecastFigure;
}
/** A "what happens next?" chart (tsfm_rc.learn, `make lessons`): history, one path per answer, what happened. */
export interface ForecastFigure {
  series: string; shock_date: string; unit: string; measure: string;
  observed: number[]; options: number[][]; realised: number[];
  answer: number; example_closest: number; qlike_by_option: number[];
  /** Pooled over every GARCH series of the fixtures, and per series. */
  similar_shocks: { n: number; closest_by_option: number[]; series: Record<string, { n: number; closest_by_option: number[] }> };
  levels: { calm_median: number; shock: number; long_run: number; persistence: number };
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

// The guided journey (site/content/journey.yaml + tasks/*.yaml, compiled by scripts/journey.mjs)
export type Os = "macos" | "windows" | "linux";
export interface JourneyStepDef {
  key: string; // "lesson:04" | "task:setup" | "site:welcome"
  kind: "lesson" | "task" | "site";
  ref: string;
  title: string;
  minutes: number | null;
  optional: boolean;
  to: string;
}
export interface PhaseDef {
  id: string; title: string; kind: "terminal" | "site"; goal: string; why: string; time: string; done: string;
  note: string | null; requires: string[]; parallel_with: string[]; requires_real_results: boolean; steps: JourneyStepDef[];
}
export interface TaskCommand {
  title: string; os: Os[]; optional: boolean; where: string | null; run: string | null; run_os: Record<Os, string> | null;
  os_note: Partial<Record<Os, string>> | null; text: string | null; expect: string | null; time: string | null;
  errors: { see: string; fix: string; source: "make doctor" | "errors.yaml" | "task" }[];
}
export interface TerminalTaskDef {
  id: string; title: string; why: string; time: string; note: string | null; long_running: boolean; before: string[];
  commands: TaskCommand[];
  check: { parser: "doctor" | "study" | "publish" | "tests"; prompt: string; success: string; auto: "real_results" | null; start_button: string | null };
}
export interface JourneyDef { welcome: { title: string; body: string }[]; phases: PhaseDef[]; tasks: Record<string, TerminalTaskDef> }

export interface ContentBundle { lessons: Lesson[]; errors: ErrorExplanation[]; journey: JourneyDef }

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
  /** What the study is, from configs/default.yaml and the contamination rule (study.json). */
  study: StudyFacts | null;
}

export interface StudyModel { name: string; label: string; hf_id: string; release_date: string; weights_date: string | null;
  effective_release: string; clean_start: string }
export interface StudyFacts {
  config: string; config_hash: string; run: string;
  data: { provider: string; tickers: number; start: string; end: string };
  targets: string[]; horizons: number[]; baselines: string[]; primary_tests: number; buffer_days: number;
  weights_dates_from: string | null; models: StudyModel[];
}
