import { useState } from "react";
import { session, store, useStore } from "../lib/app";
import { getProgress, logEvent, recordActivity, type Draft } from "../lib/progress";
import type { Lesson } from "../lib/types";
import { runner } from "../py/runner";
import { codeFor } from "./CodeCell";
import { CodeEditor } from "./CodeEditor";
import { InlineMd } from "./Markdown";
import { Output, type CellOutput } from "./Output";
import { draftId, useDraft } from "./useDraft";

export function Checkpoint({ lesson }: { lesson: Lesson }) {
  useStore();
  const ex = lesson.exercise;
  const draft = useDraft(lesson.id, "checkpoint", ex.starter);
  const id = draftId(lesson.id, "checkpoint");
  const meta = store.get<Draft>("exercise_drafts", id)?.data;
  const hints = meta?.hints_revealed ?? 0;
  const solutionViewed = meta?.solution_viewed ?? false;
  const passedBefore = (() => {
    const a = getProgress(store, lesson).activities[`${lesson.steps[lesson.steps.length - 1].id}.checkpoint1`];
    return a?.kind === "checkpoint" && a.passed;
  })();
  const [out, setOut] = useState<(CellOutput & { passed?: boolean }) | null>(null);
  const [busy, setBusy] = useState(false);
  const [showSolution, setShowSolution] = useState(false);
  const activityId = `${lesson.steps[lesson.steps.length - 1].id}.checkpoint1`;

  const setMeta = (p: Partial<Draft>) =>
    store.put<Draft>("exercise_drafts", id, { lesson_id: lesson.id, cell_id: "checkpoint", code: draft.code, hints_revealed: hints,
      solution_viewed: solutionViewed, ...p });

  const check = async () => {
    draft.save();
    setBusy(true);
    let text = "";
    setOut({ text: "", figures: [] });
    const r = await runner.check(lesson, draft.code, codeFor(lesson), (_n, t) => {
      text += t;
      setOut((o) => ({ ...(o ?? { figures: [] }), text }));
    });
    const passed = !!r.passed;
    setOut({ text: (text + (r.output ?? "")).trim() ? text : "", figures: r.figures ?? [], error: r.error, earlierFailed: r.earlierFailed, passed });
    setBusy(false);
    const now = new Date().toISOString();
    store.put("exercise_attempts", crypto.randomUUID(), { lesson_id: lesson.id, exercise_id: ex.function, code: draft.code, passed,
      hints_used: hints, solution_viewed: solutionViewed, error: r.error ? `${r.error.type}: ${r.error.message}`.slice(0, 500) : null, created_at: now });
    logEvent(store, session.id, passed ? "exercise_passed" : "exercise_failed", `${lesson.id} · ${ex.function}`);
    recordActivity(store, lesson, activityId, { kind: "checkpoint", passed, at: now, hints_used: hints, solution_viewed: solutionViewed },
      { sessionId: session.id });
  };

  const revealHint = () => {
    setMeta({ hints_revealed: Math.min(ex.hints.length, hints + 1) });
    logEvent(store, session.id, "hint", `${lesson.id} · hint ${hints + 1}`);
  };
  const revealSolution = () => {
    if (!window.confirm("Show the full solution? It is recorded that you used it; you still need to run the check.")) return;
    setMeta({ solution_viewed: true });
    setShowSolution(true);
    logEvent(store, session.id, "solution", `${lesson.id} · ${ex.function}`);
  };

  return (
    <div className="cell activity" data-testid="checkpoint">
      <div className="cell-toolbar">
        <button className="primary small" type="button" onClick={check} disabled={busy} data-testid="check">
          {busy ? "Checking…" : "✓ Check my answer"}
        </button>
        {draft.code !== ex.starter && <button className="small" type="button" onClick={draft.reset}>Reset to starter</button>}
        <span className="label">Checkpoint · write <code>{ex.function}</code> · autosaved{passedBefore ? " · ✅ passed before" : ""}</span>
      </div>
      <CodeEditor value={draft.code} onChange={draft.update} onRun={check} label="Checkpoint exercise" rows={Math.max(6, draft.code.split("\n").length + 2)} />
      {out && (
        <>
          <Output out={{ ...out, error: out.passed ? undefined : out.error }} lesson={lesson} />
          {out.passed && <div className="pass-box" data-testid="pass">✅ Passed. This lesson's flashcards join your review queue once every step is done.</div>}
          {!out.passed && !out.error && out.text && <div className="error-box">The checker did not confirm the answer.</div>}
        </>
      )}
      <div className="hints" style={{ padding: "8px 12px" }}>
        {hints > 0 && (
          <ol data-testid="hints">
            {ex.hints.slice(0, hints).map((h, i) => <li key={i}><InlineMd text={h} /></li>)}
          </ol>
        )}
        <div className="row">
          {hints < ex.hints.length && (
            <button type="button" className="small" onClick={revealHint} data-testid="hint-button">
              {hints === 0 ? "Show a hint" : `Show hint ${hints + 1} of ${ex.hints.length}`}
            </button>
          )}
          {hints >= ex.hints.length && !showSolution && (
            <button type="button" className="small" onClick={revealSolution} data-testid="solution-button">Show the full solution</button>
          )}
          <span className="muted" style={{ fontSize: "0.8rem" }}>Hints used: {hints}{solutionViewed ? " · solution viewed" : ""}</span>
        </div>
        {showSolution && (
          <div style={{ marginTop: 8 }}>
            <pre className="cmd">{ex.solution}</pre>
            <button type="button" className="small" onClick={() => draft.update(ex.solution)}>Copy into the editor</button>
          </div>
        )}
      </div>
    </div>
  );
}
