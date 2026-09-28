import contentJson from "../generated/content.json";
import runtimeJson from "../generated/runtime.json";
import statusJson from "../generated/status.json";
import type { Block, ContentBundle, Lesson, PythonBlock, ResearchStatus, Runtime } from "./types";

export const content = contentJson as unknown as ContentBundle;
export const runtime = runtimeJson as unknown as Runtime;
export const researchStatus = statusJson as unknown as ResearchStatus;
export const lessons: Lesson[] = content.lessons;

export function lessonById(id: string): Lesson | undefined {
  return lessons.find((l) => l.id === id);
}

/** Activities of a step (everything but prose). */
export function activities(blocks: Block[]) {
  return blocks.filter((b) => b.kind !== "md") as Exclude<Block, { kind: "md" }>[];
}

/** All python cells of a lesson in order (the runner executes earlier cells first). */
export function pythonCells(lesson: Lesson): PythonBlock[] {
  return lesson.steps.flatMap((s) => s.blocks.filter((b): b is PythonBlock => b.kind === "python"));
}

export function allFlashcards() {
  return lessons.flatMap((l) => l.flashcards.map((c) => ({ ...c, lessonId: l.id, lessonTitle: l.title })));
}
