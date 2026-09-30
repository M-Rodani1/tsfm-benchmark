// Spaced repetition: the SM-2 algorithm (Wozniak 1990), as used by SuperMemo 2 and, with
// small changes, by Anki. Chosen over FSRS because it is short, deterministic and fully
// auditable (this file), needs no parameters fitted to a long review history (a single
// learner with ~80 cards will not have one), and its behaviour is easy to explain to a first-
// year student: correct answers stretch the interval by the "ease" factor, lapses reset it.
// See docs/DECISIONS.md (D-048).
//
// Buttons map to SM-2 quality q (0-5): Again = 1 (failed), Hard = 3, Good = 4, Easy = 5.
//   q < 3 : repetitions = 0, interval = 1 day, lapses + 1
//   q >= 3: interval = 1, then 6, then round(interval × ease); repetitions + 1
//   ease' = max(1.3, ease + 0.1 − (5 − q)(0.08 + (5 − q) 0.02))   (applied for every answer)

export type Grade = "again" | "hard" | "good" | "easy";
export const QUALITY: Record<Grade, number> = { again: 1, hard: 3, good: 4, easy: 5 };

export interface CardState {
  card_id: string;
  lesson_id: string;
  ease: number;
  interval_days: number;
  repetitions: number;
  lapses: number;
  due: string; // local calendar date YYYY-MM-DD
  last_reviewed: string | null; // ISO timestamp
}

export function localDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function addDays(date: string, days: number): string {
  const [y, m, d] = date.split("-").map(Number);
  return localDate(new Date(y, m - 1, d + days));
}

export function newCard(card_id: string, lesson_id: string, today: string): CardState {
  return { card_id, lesson_id, ease: 2.5, interval_days: 0, repetitions: 0, lapses: 0, due: today, last_reviewed: null };
}

export function isDue(c: CardState, today: string): boolean {
  return c.due <= today;
}

export function review(c: CardState, grade: Grade, now: Date): CardState {
  const q = QUALITY[grade];
  const today = localDate(now);
  let { repetitions, interval_days, lapses } = c;
  if (q < 3) {
    repetitions = 0;
    interval_days = 1;
    lapses += 1;
  } else {
    interval_days = repetitions === 0 ? 1 : repetitions === 1 ? 6 : Math.round(interval_days * c.ease);
    repetitions += 1;
  }
  const ease = Math.max(1.3, c.ease + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02));
  return { ...c, ease: Math.round(ease * 1000) / 1000, interval_days, repetitions, lapses,
    due: addDays(today, interval_days), last_reviewed: now.toISOString() };
}

/** Next interval (days) each button would give: shown on the buttons. */
export function preview(c: CardState, now: Date): Record<Grade, number> {
  return Object.fromEntries((Object.keys(QUALITY) as Grade[]).map((g) => [g, review(c, g, now).interval_days])) as Record<Grade, number>;
}
