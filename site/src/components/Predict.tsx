import { useState } from "react";
import { session, store, useStore } from "../lib/app";
import { answerText, checkPrediction } from "../lib/predict";
import { getProgress, recordActivity } from "../lib/progress";
import type { Lesson, PredictBlock } from "../lib/types";
import { InlineMd, Markdown } from "./Markdown";

export function Predict({ lesson, block }: { lesson: Lesson; block: PredictBlock }) {
  useStore();
  const saved = getProgress(store, lesson).activities[block.id];
  const answered = saved?.kind === "predict" ? saved : null;
  const [value, setValue] = useState("");
  const q = block.data;

  const submit = (v: string | number) => {
    const correct = checkPrediction(q, v);
    recordActivity(store, lesson, block.id, { kind: "predict", answer: v, correct, at: new Date().toISOString() }, { sessionId: session.id });
  };

  return (
    <div className="predict activity" data-testid="predict" data-activity={block.id}>
      <div className="q">🤔 Predict before you run: <InlineMd text={q.question} /></div>
      {q.options ? (
        <div className="options" role="group" aria-label="Your prediction">
          {q.options.map((o, i) => {
            const chosen = answered && Number(answered.answer) === i;
            const cls = [chosen ? "chosen" : "", answered && i === q.answer ? "correct" : ""].join(" ");
            return (
              <button key={i} type="button" className={cls} disabled={!!answered} onClick={() => submit(i)} aria-pressed={!!chosen}>
                <InlineMd text={o} />
              </button>
            );
          })}
        </div>
      ) : (
        !answered && (
          <form className="row" onSubmit={(e) => { e.preventDefault(); if (value.trim()) submit(q.kind === "number" ? value.trim() : value.trim()); }}>
            <input aria-label="Your prediction" value={value} onChange={(e) => setValue(e.target.value)} inputMode={q.kind === "number" ? "decimal" : "text"}
              placeholder={q.kind === "number" ? `a number${q.unit ? ` (${q.unit})` : ""}` : "your guess"} />
            <button type="submit" className="primary">Commit my guess</button>
          </form>
        )
      )}
      {answered && (
        <div className="feedback" data-testid="predict-feedback">
          {answered.correct === true && <span className="verdict-ok">✓ Right. </span>}
          {answered.correct === false && <span className="verdict-bad">Not quite{q.options ? "" : ` (you said ${answered.answer})`}. </span>}
          {answerText(q) && <span>Answer: <strong><InlineMd text={answerText(q)} /></strong>. </span>}
          <Markdown text={q.explain} className="prose" />
          <div className="muted">Now run the code below and see.</div>
        </div>
      )}
    </div>
  );
}
