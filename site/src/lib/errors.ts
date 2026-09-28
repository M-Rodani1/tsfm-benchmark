import type { ErrorExplanation } from "./types";

export interface PyError { type: string; message: string; line?: number | null; traceback?: string }

/** Plain-English explanation: the lesson's own table first, then the general one. */
export function explainError(err: PyError, lessonErrors: ErrorExplanation[], generalErrors: ErrorExplanation[]): ErrorExplanation | null {
  const text = `${err.type}: ${err.message}`;
  for (const e of [...lessonErrors, ...generalErrors]) {
    try {
      if (new RegExp(e.match, "m").test(text)) return e;
    } catch {
      /* invalid patterns are rejected at build time */
    }
  }
  return null;
}
