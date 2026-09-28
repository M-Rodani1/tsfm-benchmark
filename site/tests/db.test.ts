import "fake-indexeddb/auto";
import { describe, expect, it } from "vitest";
import { IdbBackend, LocalStore, MemoryBackend, nextTimestamp } from "../src/lib/db";

describe("local store (IndexedDB)", () => {
  it("writes survive a reload (a new store on the same database)", async () => {
    const s1 = new LocalStore(new IdbBackend("t-reload"));
    await s1.init();
    s1.put("notes", "01", { lesson_id: "01", body: "persist me" });
    s1.put("exercise_drafts", "01:checkpoint", { lesson_id: "01", cell_id: "checkpoint", code: "def f(): pass" });
    await s1.flush();
    const s2 = new LocalStore(new IdbBackend("t-reload"));
    await s2.init();
    expect(s2.get<{ body: string }>("notes", "01")?.data.body).toBe("persist me");
    expect(s2.get<{ code: string }>("exercise_drafts", "01:checkpoint")?.data.code).toBe("def f(): pass");
    expect(s2.raw("notes", "01")?.dirty).toBe(true);
  });

  it("timestamps strictly increase per record even within one millisecond", () => {
    const t = new Date("2026-01-01T00:00:00.000Z");
    expect(nextTimestamp(t, "2026-01-01T00:00:00.000Z")).toBe("2026-01-01T00:00:00.001Z");
    expect(nextTimestamp(t)).toBe("2026-01-01T00:00:00.000Z");
  });

  it("export then import restores everything; import keeps newer local records", async () => {
    const a = new LocalStore(new MemoryBackend(), () => new Date("2026-01-01T00:00:00Z"));
    await a.init();
    a.put("notes", "01", { lesson_id: "01", body: "old" });
    a.put("flashcard_state", "01-1", { card_id: "01-1", ease: 2.5 });
    const file = JSON.parse(JSON.stringify(a.exportAll()));
    expect(file.app).toBe("tsfm-reality-check");

    const b = new LocalStore(new MemoryBackend(), () => new Date("2026-06-01T00:00:00Z"));
    await b.init();
    b.put("notes", "01", { lesson_id: "01", body: "newer on this device" });
    const res = b.importAll(file);
    expect(res).toEqual({ imported: 1, kept: 1 });
    expect(b.get<{ body: string }>("notes", "01")?.data.body).toBe("newer on this device");
    expect(b.get("flashcard_state", "01-1")).toBeDefined();
    expect(() => b.importAll({ app: "something else" })).toThrow(/not a TSFM Reality Check progress file/);
  });
});
