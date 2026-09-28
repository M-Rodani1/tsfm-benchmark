import { describe, expect, it } from "vitest";
import { LocalStore, MemoryBackend, type Rec, type Table } from "../src/lib/db";
import { resolve, syncOnce, toRow, type CursorStore, type Remote, type RemoteRow } from "../src/lib/sync";

/** In-memory server with the same last-write-wins trigger as the Postgres migration. */
class FakeServer implements Remote {
  rows = new Map<string, RemoteRow>();
  clock = 1_000;
  private key = (t: Table, id: string) => `${t}/${id}`;
  async push(table: Table, rows: RemoteRow[]) {
    for (const r of rows) {
      const old = this.rows.get(this.key(table, r.id));
      if (old && Date.parse(r.updated_at) < Date.parse(old.updated_at)) continue; // tsfm_lww()
      this.rows.set(this.key(table, r.id), { ...r, table, server_updated_at: new Date(this.clock++ * 1000).toISOString() });
    }
  }
  async pull(table: Table, since: string | null) {
    return [...this.rows.values()]
      .filter((r) => r.table === table && (!since || (r.server_updated_at as string) > since))
      .sort((a, b) => ((a.server_updated_at as string) < (b.server_updated_at as string) ? -1 : 1))
      .map(({ table: _t, ...r }) => r as RemoteRow);
  }
}

function device(start: string) {
  let t = Date.parse(start);
  const backend = new MemoryBackend();
  const store = new LocalStore(backend, () => new Date(t));
  const cursors: CursorStore = { get: async (tb) => (await backend.getMeta<string>(`c:${tb}`)) ?? null, set: (tb, v) => backend.setMeta(`c:${tb}`, v) };
  return { store, cursors, advance: (ms: number) => (t += ms) };
}

describe("sync conflict rule (last-write-wins per record)", () => {
  it("resolve(): newer updated_at wins; ties go to the server unless the local copy is dirty", () => {
    const rec = (t: string, dirty = false): Rec => ({ id: "x", data: {}, updated_at: t, deleted: false, dirty });
    expect(resolve(undefined, rec("2026-01-01T00:00:00.000Z"))).toBe("remote");
    expect(resolve(rec("2026-01-01T00:00:00.000Z"), rec("2026-01-02T00:00:00.000Z"))).toBe("remote");
    expect(resolve(rec("2026-01-03T00:00:00.000Z", true), rec("2026-01-02T00:00:00.000Z"))).toBe("local");
    expect(resolve(rec("2026-01-02T00:00:00.000Z", true), rec("2026-01-02T00:00:00.000Z"))).toBe("local");
    expect(resolve(rec("2026-01-02T00:00:00.000Z", false), rec("2026-01-02T00:00:00.000Z"))).toBe("remote");
  });

  it("two devices: changes propagate, the later edit of the same record wins everywhere", async () => {
    const server = new FakeServer();
    const a = device("2026-05-01T10:00:00Z");
    const b = device("2026-05-01T10:00:00Z");
    await a.store.init();
    await b.store.init();
    a.store.put("notes", "01", { lesson_id: "01", body: "from A" });
    await syncOnce(a.store, server, a.cursors);
    expect(a.store.dirty("notes")).toHaveLength(0);
    await syncOnce(b.store, server, b.cursors);
    expect(b.store.get<{ body: string }>("notes", "01")?.data.body).toBe("from A");

    // offline edits on both devices; B edits later
    a.advance(60_000);
    a.store.put("notes", "01", { lesson_id: "01", body: "A offline" });
    b.advance(120_000);
    b.store.put("notes", "01", { lesson_id: "01", body: "B later" });
    await syncOnce(b.store, server, b.cursors); // B pushes first
    await syncOnce(a.store, server, a.cursors); // A's older write is ignored by the server; A takes B's
    expect(a.store.get<{ body: string }>("notes", "01")?.data.body).toBe("B later");
    await syncOnce(b.store, server, b.cursors);
    expect(b.store.get<{ body: string }>("notes", "01")?.data.body).toBe("B later");
    expect(a.store.countDirty() + b.store.countDirty()).toBe(0);
  });

  it("append-only logs merge without conflicts and deletions sync as tombstones", async () => {
    const server = new FakeServer();
    const a = device("2026-05-01T10:00:00Z");
    const b = device("2026-05-01T10:00:00Z");
    await a.store.init();
    await b.store.init();
    a.store.put("review_log", "r-a", { card_id: "01-1", grade: 2 });
    b.store.put("review_log", "r-b", { card_id: "01-1", grade: 0 });
    b.store.put("notes", "02", { lesson_id: "02", body: "tmp" });
    for (const d of [a, b, a]) await syncOnce(d.store, server, d.cursors);
    expect(a.store.all("review_log").map((r) => r.id).sort()).toEqual(["r-a", "r-b"]);
    b.advance(1000);
    b.store.remove("notes", "02");
    await syncOnce(b.store, server, b.cursors);
    await syncOnce(a.store, server, a.cursors);
    expect(a.store.get("notes", "02")).toBeUndefined();
    expect(a.store.raw("notes", "02")?.deleted).toBe(true);
  });

  it("a record edited during a push stays dirty (the newer edit is not lost)", async () => {
    const d = device("2026-05-01T10:00:00Z");
    await d.store.init();
    d.store.put("notes", "01", { lesson_id: "01", body: "v1" });
    const server: Remote = {
      push: async () => {
        d.advance(10);
        d.store.put("notes", "01", { lesson_id: "01", body: "v2 typed meanwhile" });
      },
      pull: async () => [],
    };
    await syncOnce(d.store, server, d.cursors);
    expect(d.store.raw("notes", "01")?.dirty).toBe(true);
  });

  it("maps records to typed rows and back", () => {
    const rec: Rec = { id: "01", data: { lesson_id: "01", body: "x", extra: 1 }, updated_at: "2026-01-01T00:00:00.000Z", deleted: false, dirty: true };
    const row = toRow("notes", rec);
    expect(row).toEqual({ id: "01", updated_at: rec.updated_at, deleted: false, lesson_id: "01", body: "x" });
  });
});
