// Local-first store: every change is written to IndexedDB immediately (in this browser),
// then synced to Supabase when sync is configured and signed in (lib/sync.ts).
//
// Records are small (progress, notes, card states, logs), so all of them are also kept in
// memory for synchronous reads by the UI. Each record carries:
//   updated_at  client time of the last change (ISO, ms): the last-write-wins key
//   deleted     tombstone (deletions sync like any other change)
//   dirty       changed locally since the last successful push
import { openDB, type IDBPDatabase } from "idb";

export const TABLES = [
  "lesson_progress",
  "exercise_attempts",
  "exercise_drafts",
  "notes",
  "flashcard_state",
  "review_log",
  "session_log",
  "journey_state",
] as const;
export type Table = (typeof TABLES)[number];

export interface Rec<T = Record<string, unknown>> {
  id: string;
  data: T;
  updated_at: string;
  deleted: boolean;
  dirty: boolean;
}

export interface StorageBackend {
  loadAll(): Promise<Record<Table, Rec[]>>;
  putMany(table: Table, recs: Rec[]): Promise<void>;
  getMeta<T>(key: string): Promise<T | undefined>;
  setMeta(key: string, value: unknown): Promise<void>;
  clear(): Promise<void>;
}

export const DB_NAME = "tsfm-rc";
const STORES = [...TABLES, "meta"] as const;

export interface OpenHooks {
  /** Another tab still holds the old version open, so the upgrade has to wait for it. */
  onBlocked?: () => void;
  /** A newer version of the site (another tab) wants to upgrade: this connection was closed. */
  onVersionChange?: () => void;
}

/** Open the database and make sure every table has its object store.
 *
 * The version is never hard-coded. When a store is missing (a browser that last ran an older
 * version of the site, from before a table was added, or a brand-new database), the database
 * is reopened one version higher, which runs the upgrade and creates the missing stores. Data
 * in existing stores is kept. (Version 1 was hard-coded until the guided journey added
 * journey_state: every returning browser then failed to start with "object store not found".) */
export async function openStore(name: string, hooks: OpenHooks = {}): Promise<IDBPDatabase> {
  const onVersionChange = (db: IDBPDatabase) => () => {
    db.close();
    hooks.onVersionChange?.();
  };
  let db = await openDB(name);
  db.addEventListener("versionchange", onVersionChange(db));
  if (STORES.every((t) => db.objectStoreNames.contains(t))) return db;
  const version = db.version + 1;
  db.close();
  db = await openDB(name, version, {
    upgrade(up) {
      for (const t of TABLES) if (!up.objectStoreNames.contains(t)) up.createObjectStore(t, { keyPath: "id" });
      if (!up.objectStoreNames.contains("meta")) up.createObjectStore("meta");
    },
    blocked: () => hooks.onBlocked?.(),
  });
  db.addEventListener("versionchange", onVersionChange(db));
  return db;
}

export class IdbBackend implements StorageBackend {
  private db: Promise<IDBPDatabase>;
  private handle: IDBPDatabase | null = null;
  constructor(name = DB_NAME, hooks: OpenHooks = {}) {
    this.db = openStore(name, hooks);
    void this.db.then((db) => (this.handle = db)).catch(() => {});
  }
  async loadAll() {
    const db = await this.db;
    const out = {} as Record<Table, Rec[]>;
    for (const t of TABLES) out[t] = (await db.getAll(t)) as Rec[];
    return out;
  }
  /** Starts the transaction synchronously (once the database is open) and commits it at once,
   * so a write made just before the tab is reloaded or closed is not left waiting in a queue.
   * IndexedDB runs read-write transactions on the same store in the order they were created. */
  putMany(table: Table, recs: Rec[]): Promise<void> {
    const write = (db: IDBPDatabase) => {
      const tx = db.transaction(table, "readwrite");
      for (const r of recs) tx.store.put(r).catch(() => {}); // a failure also rejects tx.done
      tx.commit?.();
      return tx.done;
    };
    return this.handle ? write(this.handle) : this.db.then(write);
  }
  async getMeta<T>(key: string) {
    return (await (await this.db).get("meta", key)) as T | undefined;
  }
  async setMeta(key: string, value: unknown) {
    await (await this.db).put("meta", value, key);
  }
  async clear() {
    const db = await this.db;
    for (const t of [...TABLES, "meta"]) await db.clear(t);
  }
  /** Close the connection (tests: stands in for the page going away). */
  async close() {
    (await this.db).close();
  }
}

export class MemoryBackend implements StorageBackend {
  data = Object.fromEntries(TABLES.map((t) => [t, new Map<string, Rec>()])) as Record<Table, Map<string, Rec>>;
  meta = new Map<string, unknown>();
  async loadAll() {
    return Object.fromEntries(TABLES.map((t) => [t, [...this.data[t].values()].map((r) => ({ ...r }))])) as Record<Table, Rec[]>;
  }
  async putMany(table: Table, recs: Rec[]) {
    for (const r of recs) this.data[table].set(r.id, structuredClone(r));
  }
  async getMeta<T>(key: string) {
    return this.meta.get(key) as T | undefined;
  }
  async setMeta(key: string, value: unknown) {
    this.meta.set(key, value);
  }
  async clear() {
    for (const t of TABLES) this.data[t].clear();
    this.meta.clear();
  }
}

/** Strictly increasing ISO timestamp for a record: never equal to or before its previous one. */
export function nextTimestamp(now: Date, previous?: string): string {
  let t = now.getTime();
  if (previous) t = Math.max(t, Date.parse(previous) + 1);
  return new Date(t).toISOString();
}

export interface ExportFile {
  app: "tsfm-reality-check";
  schema: 1;
  exported_utc: string;
  tables: Record<Table, Omit<Rec, "dirty">[]>;
}

export class LocalStore {
  private maps = Object.fromEntries(TABLES.map((t) => [t, new Map<string, Rec>()])) as Record<Table, Map<string, Rec>>;
  private listeners = new Set<() => void>();
  private pending = new Set<Promise<void>>();
  version = 0;
  ready = false;
  lastError: string | null = null;

  constructor(readonly backend: StorageBackend, private clock: () => Date = () => new Date()) {}

  async init() {
    const all = await this.backend.loadAll();
    for (const t of TABLES) for (const r of all[t] ?? []) this.maps[t].set(r.id, r);
    this.ready = true;
    this.bump();
  }

  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };
  getVersion = () => this.version;
  private bump() {
    this.version++;
    for (const fn of this.listeners) fn();
  }

  // Every change starts its IndexedDB write immediately (not queued behind earlier writes),
  // so nothing is lost if the tab is reloaded or closed right after an action.
  private persist(table: Table, recs: Rec[]) {
    const copy = recs.map((r) => structuredClone(r));
    const p: Promise<void> = this.backend
      .putMany(table, copy)
      .catch((e) => {
        this.lastError = String(e);
        console.error("local save failed", e);
      })
      .finally(() => this.pending.delete(p));
    this.pending.add(p);
  }

  /** Resolves when every write so far has reached IndexedDB. */
  async flush() {
    while (this.pending.size) await Promise.all([...this.pending]);
  }

  /** Show a storage problem to the learner (the layout displays lastError). */
  setError(message: string) {
    this.lastError = message;
    this.bump();
  }

  get<T>(table: Table, id: string): Rec<T> | undefined {
    const r = this.maps[table].get(id);
    return r && !r.deleted ? (r as Rec<T>) : undefined;
  }
  raw(table: Table, id: string): Rec | undefined {
    return this.maps[table].get(id);
  }
  all<T>(table: Table): Rec<T>[] {
    return [...this.maps[table].values()].filter((r) => !r.deleted) as Rec<T>[];
  }
  dirty(table: Table): Rec[] {
    return [...this.maps[table].values()].filter((r) => r.dirty);
  }
  countDirty(): number {
    return TABLES.reduce((n, t) => n + this.dirty(t).length, 0);
  }

  put<T extends object>(table: Table, id: string, data: T): Rec<T> {
    const prev = this.maps[table].get(id);
    const rec: Rec<T> = { id, data, updated_at: nextTimestamp(this.clock(), prev?.updated_at), deleted: false, dirty: true };
    this.maps[table].set(id, rec as Rec);
    this.persist(table, [rec as Rec]);
    this.bump();
    return rec;
  }

  patch<T extends object>(table: Table, id: string, partial: Partial<T>, initial: T): Rec<T> {
    const prev = this.get<T>(table, id);
    return this.put<T>(table, id, { ...(prev?.data ?? initial), ...partial });
  }

  remove(table: Table, id: string) {
    const prev = this.maps[table].get(id);
    if (!prev || prev.deleted) return;
    const rec: Rec = { ...prev, updated_at: nextTimestamp(this.clock(), prev.updated_at), deleted: true, dirty: true };
    this.maps[table].set(id, rec);
    this.persist(table, [rec]);
    this.bump();
  }

  /** Store records that came from the server (already resolved by the sync rule): not dirty. */
  applyRemote(table: Table, recs: Rec[]) {
    if (!recs.length) return;
    for (const r of recs) this.maps[table].set(r.id, { ...r, dirty: false });
    this.persist(table, recs.map((r) => ({ ...r, dirty: false })));
    this.bump();
  }

  /** After a successful push: clean, unless the record changed again meanwhile. */
  markClean(table: Table, pushed: { id: string; updated_at: string }[]) {
    const changed: Rec[] = [];
    for (const p of pushed) {
      const r = this.maps[table].get(p.id);
      if (r && r.dirty && r.updated_at === p.updated_at) {
        r.dirty = false;
        changed.push(r);
      }
    }
    if (changed.length) {
      this.persist(table, changed);
      this.bump();
    }
  }

  markAllDirty() {
    for (const t of TABLES) {
      const recs = [...this.maps[t].values()];
      for (const r of recs) r.dirty = true;
      if (recs.length) this.persist(t, recs);
    }
    this.bump();
  }

  exportAll(): ExportFile {
    const tables = Object.fromEntries(
      TABLES.map((t) => [t, [...this.maps[t].values()].map(({ dirty: _dirty, ...r }) => r)]),
    ) as ExportFile["tables"];
    return { app: "tsfm-reality-check", schema: 1, exported_utc: this.clock().toISOString(), tables };
  }

  /** Merge an export: for each record the newer `updated_at` wins (same rule as sync).
   * Imported records that win are marked dirty so they reach the server too. */
  importAll(file: unknown): { imported: number; kept: number } {
    const f = file as ExportFile;
    if (!f || f.app !== "tsfm-reality-check" || f.schema !== 1 || typeof f.tables !== "object")
      throw new Error("This is not a TSFM Reality Check progress file (schema 1).");
    let imported = 0;
    let kept = 0;
    for (const t of TABLES) {
      const incoming = f.tables[t] ?? [];
      const winners: Rec[] = [];
      for (const r of incoming) {
        if (typeof r?.id !== "string" || typeof r?.updated_at !== "string" || isNaN(Date.parse(r.updated_at)))
          throw new Error(`Malformed record in table ${t}.`);
        const cur = this.maps[t].get(r.id);
        if (!cur || Date.parse(r.updated_at) > Date.parse(cur.updated_at)) {
          const rec: Rec = { id: r.id, data: r.data ?? {}, updated_at: r.updated_at, deleted: !!r.deleted, dirty: true };
          this.maps[t].set(r.id, rec);
          winners.push(rec);
          imported++;
        } else kept++;
      }
      if (winners.length) this.persist(t, winners);
    }
    this.bump();
    return { imported, kept };
  }

  async resetAll() {
    for (const t of TABLES) this.maps[t].clear();
    await this.flush();
    await this.backend.clear();
    this.bump();
  }
}
