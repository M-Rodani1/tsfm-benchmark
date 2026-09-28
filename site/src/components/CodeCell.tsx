import { useState } from "react";
import { session, store } from "../lib/app";
import { recordActivity } from "../lib/progress";
import type { Lesson, PythonBlock } from "../lib/types";
import { runner } from "../py/runner";
import { CodeEditor } from "./CodeEditor";
import { Output, type CellOutput } from "./Output";
import { savedCode, useDraft } from "./useDraft";

export function codeFor(lesson: Lesson) {
  return (cellId: string) => {
    const block = lesson.steps.flatMap((s) => s.blocks).find((b) => b.kind === "python" && b.id === cellId) as PythonBlock | undefined;
    return savedCode(lesson.id, cellId, block?.text ?? "");
  };
}

export function CodeCell({ lesson, block }: { lesson: Lesson; block: PythonBlock }) {
  const draft = useDraft(lesson.id, block.id, block.text);
  const [out, setOut] = useState<CellOutput | null>(null);
  const [running, setRunning] = useState(false);
  const edited = draft.code !== block.text;

  const run = async () => {
    draft.save();
    setRunning(true);
    let text = "";
    setOut({ text: "", figures: [] });
    const r = await runner.runCell(lesson, block.id, draft.code, codeFor(lesson), (_name, t) => {
      text += t;
      setOut((o) => ({ ...(o ?? { figures: [] }), text }));
    });
    setOut({ text, value: r.value, figures: r.figures ?? [], error: r.error, earlierFailed: r.earlierFailed });
    setRunning(false);
    recordActivity(store, lesson, block.id, { kind: "python", ok: r.ok, at: new Date().toISOString() }, { sessionId: session.id });
  };

  return (
    <div className="cell activity" data-testid="code-cell" data-cell={block.id}>
      <div className="cell-toolbar">
        <button className="primary small" type="button" onClick={run} disabled={running} data-testid="run">
          {running ? "Running…" : "▶ Run"}
        </button>
        {edited && <button className="small" type="button" onClick={draft.reset}>Reset to original</button>}
        <span className="label">Python · editable · Shift+Enter runs{edited ? " · edited (autosaved)" : ""}</span>
      </div>
      <CodeEditor value={draft.code} onChange={draft.update} onRun={run} label={`Code cell ${block.id}`} />
      {out && <Output out={out} lesson={lesson} />}
    </div>
  );
}
