import { describe, expect, it } from "vitest";
import { addDays, isDue, localDate, newCard, preview, review } from "../src/lib/srs";

const day = (s: string) => new Date(`${s}T09:00:00`);

describe("SM-2 scheduler", () => {
  it("follows the SM-2 interval sequence 1, 6, round(6 × ease) for good answers", () => {
    let c = newCard("01-1", "01", "2026-03-01");
    expect(isDue(c, "2026-03-01")).toBe(true);
    c = review(c, "good", day("2026-03-01"));
    expect([c.interval_days, c.repetitions, c.due]).toEqual([1, 1, "2026-03-02"]);
    c = review(c, "good", day("2026-03-02"));
    expect([c.interval_days, c.due]).toEqual([6, "2026-03-08"]);
    c = review(c, "good", day("2026-03-08"));
    expect(c.interval_days).toBe(Math.round(6 * 2.5)); // ease stays 2.5 for q = 4
    expect(c.ease).toBe(2.5);
    expect(isDue(c, "2026-03-22")).toBe(false);
    expect(isDue(c, "2026-03-23")).toBe(true);
  });

  it("updates ease with the SM-2 formula and never below 1.3", () => {
    const c = newCard("x", "01", "2026-03-01");
    expect(review(c, "easy", day("2026-03-01")).ease).toBeCloseTo(2.6); // q=5: +0.1
    expect(review(c, "hard", day("2026-03-01")).ease).toBeCloseTo(2.36); // q=3: -0.14
    expect(review(c, "again", day("2026-03-01")).ease).toBeCloseTo(1.96); // q=1: -0.54
    let low = c;
    for (let i = 0; i < 10; i++) low = review(low, "again", day("2026-03-01"));
    expect(low.ease).toBe(1.3);
  });

  it("resets repetitions after a lapse and counts it", () => {
    let c = newCard("x", "01", "2026-03-01");
    c = review(c, "good", day("2026-03-01"));
    c = review(c, "good", day("2026-03-02"));
    c = review(c, "again", day("2026-03-08"));
    expect([c.repetitions, c.interval_days, c.lapses, c.due]).toEqual([0, 1, 1, "2026-03-09"]);
  });

  it("previews the interval of each button and handles month ends", () => {
    const c = { ...newCard("x", "01", "2026-01-31"), repetitions: 2, interval_days: 6 };
    const p = preview(c, day("2026-01-31"));
    expect(p.again).toBe(1);
    expect(p.good).toBe(15);
    expect(addDays("2026-01-31", 1)).toBe("2026-02-01");
    expect(localDate(new Date(2026, 11, 31))).toBe("2026-12-31");
  });
});
