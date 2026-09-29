import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { Page } from "@playwright/test";

export interface LessonJson {
  id: string; slug: string; title: string; steps: { id: string; title: string; blocks: { kind: string; id?: string; text?: string }[] }[];
  exercise: { function: string; starter: string; solution: string }; flashcards: { id: string; q: string; a: string }[];
}

export const content = JSON.parse(readFileSync(fileURLToPath(new URL("../src/generated/content.json", import.meta.url)), "utf8")) as { lessons: LessonJson[] };

export function localDate(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** A progress file (the site's own export format) with the given records. Unless the test sets
 * journey_state itself, the welcome tour counts as seen, so Home does not redirect to it. */
export function progressFile(tables: Record<string, { id: string; data: object }[]>) {
  const now = new Date().toISOString();
  const all = ["lesson_progress", "exercise_attempts", "exercise_drafts", "notes", "flashcard_state", "review_log", "session_log", "journey_state"];
  tables = { journey_state: [tourSeen], ...tables };
  return {
    app: "tsfm-reality-check", schema: 1, exported_utc: now,
    tables: Object.fromEntries(all.map((t) => [t, (tables[t] ?? []).map((r) => ({ ...r, updated_at: now, deleted: false }))])),
  };
}

export const tourSeen = { id: "site:welcome", data: { step_key: "site:welcome", status: "done", method: "site", detail: "test", started_at: null, done_at: null } };

/** Skip the first-visit tour (tests that are not about it). */
export async function skipTour(page: Page) {
  await page.goto("/welcome");
  await page.getByTestId("welcome-skip").click();
  await page.getByTestId("next-action").waitFor();
}

export async function importProgress(page: Page, file: object) {
  await page.goto("/account");
  await page.getByTestId("import-file").setInputFiles({ name: "progress.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(file)) });
  await page.getByTestId("account-message").filter({ hasText: "Imported" }).waitFor();
}

/** Can this machine download Pyodide's packages from the CDN? */
export async function cdnReachable(): Promise<boolean> {
  try {
    const r = await fetch("https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide-lock.json", { signal: AbortSignal.timeout(8000) });
    return r.ok;
  } catch {
    return false;
  }
}
