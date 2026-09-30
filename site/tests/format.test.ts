import { describe, expect, it } from "vitest";
import { fmtDate, fmtDuration, fmtMoment, numberWord } from "../src/lib/format";

describe("display formats", () => {
  it("dates read '26 Nov 2024' whatever the browser locale", () => {
    expect(fmtDate("2024-11-26")).toBe("26 Nov 2024");
    expect(fmtDate("2025-09-15")).toBe("15 Sep 2025");
    expect(fmtDate("2024-07-30T00:00:00")).toBe("30 Jul 2024");
    expect(fmtDate("not a date")).toBe("not a date");
  });
  it("moments show the time today and the day otherwise", () => {
    const now = new Date(2026, 8, 29, 16, 0);
    expect(fmtMoment(new Date(2026, 8, 29, 14, 5).toISOString(), now)).toBe("14:05");
    expect(fmtMoment(new Date(2026, 8, 28, 9, 0).toISOString(), now)).toBe("28 Sep, 09:00");
  });
  it("durations and small counts", () => {
    expect(fmtDuration(160 * 60)).toBe("2 h 40 min");
    expect(fmtDuration(45 * 60)).toBe("45 min");
    expect(numberWord(9)).toBe("nine");
    expect(numberWord(27)).toBe("27");
  });
});
