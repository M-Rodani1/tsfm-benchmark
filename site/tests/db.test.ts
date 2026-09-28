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

  it("writes made right before the page goes away are not lost (each starts its transaction at once)", async () => {
    const b1 = new IdbBackend("t-unload");
    const s1 = new LocalStore(b1);
    await s1.init();
    for (let i = 0; i < 5; i++) {
      s1.put("flashcard_state", `00-${i}`, { card_id: `00-${i}`, due: "2026-10-01" });
      s1.put("review_log", `r${i}`, { card_id: `00-${i}` });
    }
    // no flush: the connection closes immediately, as when the tab is reloaded. Transactions
    // already created still commit; writes still queued in JavaScript would be lost.
    await b1.close();
    const s2 = new LocalStore(new IdbBackend("t-unload"));
    await s2.init();
    expect(s2.all("flashcard_state")).toHaveLength(5);
    expect(s2.all("review_log")).toHaveLength(5);
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
