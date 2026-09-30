// Editable code with autosave: every keystroke updates the screen at once and is written to
// the local store 400 ms after typing stops (and immediately when the page is hidden/closed).
import { useCallback, useEffect, useRef, useState } from "react";
import { store } from "../lib/app";
import type { Draft } from "../lib/progress";

export function draftId(lessonId: string, cellId: string) {
  return `${lessonId}:${cellId}`;
}

export function savedCode(lessonId: string, cellId: string, original: string): string {
  return store.get<Draft>("exercise_drafts", draftId(lessonId, cellId))?.data.code ?? original;
}

export function useDraft(lessonId: string, cellId: string, original: string) {
  const id = draftId(lessonId, cellId);
  const [code, setCode] = useState(() => savedCode(lessonId, cellId, original));
  const pending = useRef<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const save = useCallback(() => {
    if (pending.current === null) return;
    const prev = store.get<Draft>("exercise_drafts", id)?.data;
    store.put<Draft>("exercise_drafts", id, { lesson_id: lessonId, cell_id: cellId, code: pending.current,
      hints_revealed: prev?.hints_revealed ?? 0, solution_viewed: prev?.solution_viewed ?? false });
    pending.current = null;
  }, [id, lessonId, cellId]);

  useEffect(() => {
    const onHide = () => save();
    window.addEventListener("pagehide", onHide);
    document.addEventListener("visibilitychange", onHide);
    return () => {
      save();
      window.removeEventListener("pagehide", onHide);
      document.removeEventListener("visibilitychange", onHide);
    };
  }, [save]);

  const update = (v: string) => {
    setCode(v);
    pending.current = v;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(save, 400);
  };
  const reset = () => update(original);
  return { code, update, reset, save };
}
