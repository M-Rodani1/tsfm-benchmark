// Sync between the local store (IndexedDB) and Supabase (Postgres).
//
// Conflict rule (documented in docs/DECISIONS.md D-047 and docs/DEPLOY.md):
//   last-write-wins per record, by the client timestamp `updated_at`.
//   - push: every dirty record is upserted; a server trigger ignores an update whose
//     updated_at is older than the stored one, so a stale device can never overwrite a newer
//     change (tsfm_lww() in site/supabase/migrations).
//   - pull: rows changed on the server since the last pull (server_updated_at cursor, with a
//     small overlap) replace the local record if their updated_at is newer, or equal and the
//     local copy is not dirty. A newer local dirty record is kept (and pushed next).
//   - append-only tables (exercise_attempts, review_log) have unique ids: no conflicts.
// Deletions are tombstones (deleted = true) and follow the same rule.
import type { LocalStore, Rec, Table } from "./db";
import { TABLES } from "./db";

/** Typed columns of each table (besides id, user_id, updated_at, server_updated_at, deleted). */
export const COLUMNS: Record<Table, string[]> = {
  lesson_progress: ["lesson_id", "status", "current_step", "completed_steps", "activities", "prereq_override", "started_at", "completed_at"],
  exercise_attempts: ["lesson_id", "exercise_id", "code", "passed", "hints_used", "solution_viewed", "error", "created_at"],
  exercise_drafts: ["lesson_id", "cell_id", "code", "hints_revealed", "solution_viewed"],
  notes: ["lesson_id", "body"],
  flashcard_state: ["card_id", "lesson_id", "ease", "interval_days", "repetitions", "lapses", "due", "last_reviewed"],
  review_log: ["card_id", "grade", "reviewed_at", "interval_before", "interval_after", "ease_before", "ease_after"],
  session_log: ["started_at", "ended_at", "active_seconds", "events"],
  journey_state: ["step_key", "status", "method", "detail", "started_at", "done_at"],
};

export interface RemoteRow {
  id: string;
  updated_at: string;
  deleted: boolean;
  server_updated_at?: string;
  [column: string]: unknown;
}

export interface Remote {
  push(table: Table, rows: RemoteRow[]): Promise<void>;
  /** Rows with server_updated_at > since (all rows if since is null), oldest first. */
  pull(table: Table, since: string | null): Promise<RemoteRow[]>;
}

export interface CursorStore {
  get(table: Table): Promise<string | null>;
  set(table: Table, value: string): Promise<void>;
}

export const PULL_OVERLAP_MS = 5_000;

export function toRow(table: Table, rec: Rec): RemoteRow {
  const row: RemoteRow = { id: rec.id, updated_at: rec.updated_at, deleted: rec.deleted };
  for (const c of COLUMNS[table]) row[c] = (rec.data as Record<string, unknown>)[c] ?? null;
  return row;
}

export function fromRow(table: Table, row: RemoteRow): Rec {
  const data: Record<string, unknown> = {};
  for (const c of COLUMNS[table]) if (row[c] !== null && row[c] !== undefined) data[c] = row[c];
  return { id: row.id, data, updated_at: new Date(row.updated_at).toISOString(), deleted: !!row.deleted, dirty: false };
}

/** Which copy wins: "remote" replaces the local record, "local" keeps it. */
export function resolve(local: Rec | undefined, remote: Rec): "remote" | "local" {
  if (!local) return "remote";
  const l = Date.parse(local.updated_at);
  const r = Date.parse(remote.updated_at);
  if (r > l) return "remote";
  if (r === l && !local.dirty) return "remote";
  return "local";
}

export interface SyncReport {
  pushed: number;
  pulled: number;
  keptLocal: number;
}

export async function syncOnce(store: LocalStore, remote: Remote, cursors: CursorStore): Promise<SyncReport> {
  const report: SyncReport = { pushed: 0, pulled: 0, keptLocal: 0 };
  for (const table of TABLES) {
    const dirty = store.dirty(table).map((r) => ({ ...r }));
    if (dirty.length) {
      for (let i = 0; i < dirty.length; i += 200) {
        const chunk = dirty.slice(i, i + 200);
        await remote.push(table, chunk.map((r) => toRow(table, r)));
        store.markClean(table, chunk);
      }
      report.pushed += dirty.length;
    }
    const since = await cursors.get(table);
    const sinceWithOverlap = since ? new Date(Date.parse(since) - PULL_OVERLAP_MS).toISOString() : null;
    const rows = await remote.pull(table, sinceWithOverlap);
    const winners: Rec[] = [];
    let maxCursor = since;
    for (const row of rows) {
      const rec = fromRow(table, row);
      if (resolve(store.raw(table, rec.id), rec) === "remote") {
        if (store.raw(table, rec.id)?.updated_at !== rec.updated_at || store.raw(table, rec.id)?.dirty) winners.push(rec);
      } else report.keptLocal++;
      if (row.server_updated_at && (!maxCursor || row.server_updated_at > maxCursor)) maxCursor = row.server_updated_at;
    }
    store.applyRemote(table, winners);
    report.pulled += winners.length;
    if (maxCursor && maxCursor !== since) await cursors.set(table, maxCursor);
  }
  return report;
}
