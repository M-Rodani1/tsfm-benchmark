import type { PredictData } from "./types";

/** true/false for gradable predictions; null for free-text ones (recorded, not graded). */
export function checkPrediction(p: PredictData, value: string | number): boolean | null {
  if (p.options && p.options.length) return Number(value) === p.answer;
  if (p.kind === "number" && typeof p.answer === "number") {
    const v = typeof value === "number" ? value : parseFloat(String(value).replace(",", "."));
    if (!Number.isFinite(v)) return false;
    return Math.abs(v - p.answer) <= (p.tolerance ?? 0) + 1e-9;
  }
  return null;
}

export function answerText(p: PredictData): string {
  if (p.options && typeof p.answer === "number") return p.options[p.answer];
  if (p.answer !== undefined) return `${p.answer}${p.unit ?? ""}`;
  return "";
}
