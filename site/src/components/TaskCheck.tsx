// The check of a terminal task's pasted output (lib/cliparse.ts), shared by the task page and
// Home's "It has finished" dialog. Only the parser's summary is stored, never the pasted text.
import { useState } from "react";
import { session, store } from "../lib/app";
import { CHECKERS, type CheckResult } from "../lib/cliparse";
import { content } from "../lib/content";
import type { JourneyRecord, StepView } from "../lib/journey";
import { markDone, markStarted, resetStep } from "../lib/journeyState";
import { InlineMd } from "./Markdown";

const VERDICT_WORD: Record<CheckResult["verdict"], string> = { success: "Checked", failure: "Not yet", partial: "Part of the way", unrecognised: "Not recognised" };

export function TaskCheck({ taskId, step, allowSelfReport = true, allowReset = true, headingLevel = 2 }: {
  taskId: string; step: StepView; allowSelfReport?: boolean; allowReset?: boolean; headingLevel?: 2 | 3;
}) {
  const task = content.journey.tasks[taskId];
  const key = `task:${taskId}`;
  const [text, setText] = useState("");
  const [result, setResult] = useState<CheckResult | null>(null);
  const rec = store.get<JourneyRecord>("journey_state", key)?.data;
  const check = () => {
    const r = CHECKERS[task.check.parser](text, content.errors);
    setResult(r);
    if (r.verdict === "success") markDone(store, key, "output", r.detail, session.id);
    else if (r.verdict === "partial" && task.long_running) markStarted(store, key, session.id);
  };
  const selfReport = () => {
    if (!window.confirm("Mark this step as done without a checked output? It will be shown as self-reported.")) return;
    markDone(store, key, "self-reported", "self-reported", session.id);
  };
  const H = headingLevel === 2 ? "h2" : "h3";
  return (
    <section className="check" id="check" data-testid="task-check" aria-labelledby={`check-${taskId}`}>
      <H id={`check-${taskId}`}>Check the output</H>
      <p><InlineMd text={task.check.prompt} /></p>
      <p className="sub">Success looks like: <InlineMd text={task.check.success} /> Only this summary is stored, never the text you paste.</p>
      <textarea rows={8} value={text} onChange={(e) => setText(e.target.value)} spellCheck={false}
        placeholder="Paste the terminal output here" aria-label="Pasted terminal output" data-testid="task-output" />
      <div className="row">
        <button type="button" className="primary" onClick={check} disabled={!text.trim()} data-testid="task-check-button">Check</button>
        {!text.trim() && <span className="predict-hint">Paste the output first.</span>}
        <span className="spacer" />
        {allowSelfReport && !step.done && (
          <button type="button" className="small" onClick={selfReport} data-testid="task-self-report">I've done this (self-reported)</button>
        )}
        {allowReset && rec && step.method !== "auto" && (
          <button type="button" className="small" onClick={() => { resetStep(store, key); setResult(null); }} data-testid="task-reset">Reset this step</button>
        )}
      </div>
      <div aria-live="polite">
        {result && (
          <div className={`check-result ${result.verdict}`} data-testid="task-result" data-verdict={result.verdict}>
            <p className="v" style={{ margin: 0 }}>{result.verdict === "success" ? "✓ " : result.verdict === "failure" ? "✗ " : ""}{VERDICT_WORD[result.verdict]}: <InlineMd text={result.summary} /></p>
            {result.problems.length > 0 && (
              <ul>
                {result.problems.map((p, i) => (
                  <li key={i}>
                    <InlineMd text={p.title} />{p.detail && <div className="sub"><InlineMd text={p.detail} /></div>}
                    {p.fix && <div>→ <InlineMd text={p.fix} /></div>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
