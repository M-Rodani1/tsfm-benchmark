// "Predict, then check". Choose an answer (native radios in a fieldset), then check it; the result
// is announced (aria-live) with the explanation. For a chart question the chosen answer is drawn
// as a blue dashed forecast and, on check, what happened draws in as a solid graphite line.
// The first checked answer is what is stored; "Try again" lets you explore without changing it.
import { useId, useRef, useState } from "react";
import { session, store, useStore } from "../lib/app";
import { answerText, checkPrediction } from "../lib/predict";
import { getProgress, recordActivity } from "../lib/progress";
import type { ForecastFigure, Lesson, PredictBlock } from "../lib/types";
import { ForecastChart } from "./ForecastChart";
import { InlineMd, Markdown } from "./Markdown";

function Tag({ kind }: { kind: "forecast" | "happened" | "both" | "answer" | "forecast-answer" }) {
  const text = { forecast: "Your forecast", happened: "What happened", both: "Your forecast, and what happened", answer: "Answer",
    "forecast-answer": "Your forecast, and the answer" }[kind];
  const dashed = kind === "forecast" || kind === "both" || kind === "forecast-answer";
  return (
    <span className={`tag ${dashed ? "forecast" : "happened"}`} data-testid="option-tag">
      <svg viewBox="0 0 18 6" aria-hidden="true">
        <line x1="0" x2="18" y1="3" y2="3" stroke={dashed ? "var(--forecast)" : "var(--observed)"} strokeWidth="2" strokeDasharray={dashed ? "4 3" : undefined} />
      </svg>
      {text}
    </span>
  );
}

/** "Across all 73 similar shocks …": the evidence behind a chart question's answer, from its figure. */
function evidence(fig: ForecastFigure, options: string[]): string {
  const t = fig.similar_shocks.closest_by_option;
  const series = Object.keys(fig.similar_shocks.series).length;
  const times = (k: number) => (k === 0 ? "never" : k === 1 ? "once" : `${k} times`);
  const rest = options.map((o, i) => ({ o, k: t[i], i })).filter((x) => x.i !== fig.answer).map((x) => `“${x.o}” ${times(x.k)}`).join(" and ");
  const example = fig.example_closest === fig.answer ? "This example is one of them." : `This example was an exception: it ended closest to “${options[fig.example_closest]}”.`;
  return `Across all ${fig.similar_shocks.n} similar shocks in the ${series} GARCH series of the course fixtures, “${options[fig.answer]}” came closest ` +
    `${times(t[fig.answer])}, ${rest}. “Closest” means the lowest QLIKE, the loss the study uses for volatility. ${example}`;
}

/** Move to what comes after this question: the next activity of the step, or the step's Next. */
function continueFrom(el: HTMLElement | null) {
  const step = el?.closest("[data-testid=step]");
  if (!step || !el) return;
  const targets = [...step.querySelectorAll<HTMLElement>(".activity, [data-next-target]")];
  const next = targets[targets.indexOf(el) + 1] ?? step.querySelector<HTMLElement>("[data-next-target]");
  if (!next) return;
  next.scrollIntoView({ block: "center", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  const focusable = next.matches("a, button") ? next : next.querySelector<HTMLElement>("button:not(:disabled), textarea, a, input");
  focusable?.focus({ preventScroll: true });
}

export function Predict({ lesson, block }: { lesson: Lesson; block: PredictBlock }) {
  useStore();
  const saved = getProgress(store, lesson).activities[block.id];
  const answered = saved?.kind === "predict" ? saved : null;
  const q = block.data;
  const fig = q.figureData ?? null;
  const root = useRef<HTMLDivElement>(null);
  const name = useId();
  const hintId = useId();
  // local view: the answer being considered, and whether it has been checked
  const [choice, setChoice] = useState<number | null>(answered && q.options ? Number(answered.answer) : null);
  const [value, setValue] = useState(answered && !q.options ? String(answered.answer) : "");
  const [revealed, setRevealed] = useState(!!answered);
  const [animate, setAnimate] = useState(false);
  const [explored, setExplored] = useState(false); // checked again after "Try again" (not stored)

  const given: string | number | null = q.options ? choice : value.trim() || null;
  const correct = revealed && given !== null ? checkPrediction(q, given) : null;
  const check = () => {
    if (given === null) return;
    if (!answered) recordActivity(store, lesson, block.id, { kind: "predict", answer: given, correct: checkPrediction(q, given), at: new Date().toISOString() },
      { sessionId: session.id });
    else setExplored(true);
    setRevealed(true);
    setAnimate(true);
  };
  const tryAgain = () => {
    setRevealed(false);
    setAnimate(false);
    setChoice(null);
    setValue("");
    root.current?.querySelector<HTMLInputElement>("input")?.focus();
  };
  const tagFor = (i: number) => {
    const mine = i === choice;
    const right = revealed && i === q.answer;
    if (mine && right) return fig ? "both" : "forecast-answer";
    if (mine) return "forecast";
    if (right) return fig ? "happened" : "answer";
    return null;
  };
  const checkLabel = fig ? "Check what happened" : "Check my answer";
  const r = fig?.realised ?? [];

  return (
    <div className="predict activity" data-testid="predict" data-activity={block.id} ref={root}>
      {fig && <ForecastChart fig={fig} selected={choice} revealed={revealed} animate={animate} />}
      <fieldset>
        <legend>{!fig && <span className="kicker">Predict before you run the code</span>}<InlineMd text={q.question} /></legend>
        {q.options ? (
          <div className="options">
            {q.options.map((o, i) => {
              const tag = tagFor(i);
              return (
                <label key={i} className={`option${i === choice ? " selected" : ""}${revealed ? " locked" : ""}`}>
                  <input type="radio" name={name} value={i} checked={choice === i} disabled={revealed} onChange={() => setChoice(i)} />
                  <span className="text"><InlineMd text={o} /></span>
                  {tag && <span className="tags"><Tag kind={tag} /></span>}
                </label>
              );
            })}
          </div>
        ) : (
          <div className="predict-input">
            <input aria-label="Your prediction" value={value} disabled={revealed} onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); check(); } }}
              inputMode={q.kind === "number" ? "decimal" : "text"} placeholder={q.kind === "number" ? `a number${q.unit ? ` (${q.unit})` : ""}` : "your guess"} />
          </div>
        )}
      </fieldset>
      {!revealed && (
        <div className="predict-actions">
          <button type="button" className="primary" onClick={check} disabled={given === null} aria-describedby={given === null ? hintId : undefined}
            data-testid="predict-check">{checkLabel}</button>
          {given === null && <span className="predict-hint" id={hintId}>{q.options ? "Choose an answer first." : "Write your guess first."}</span>}
        </div>
      )}
      <div aria-live="polite">
        {revealed && (
          <div className="predict-result" data-testid="predict-feedback" data-correct={correct === null ? "unknown" : String(correct)}>
            <p className={`verdict ${correct ? "right" : "wrong"}`}>
              {correct === true ? "✓ Right." : correct === false ? `Not quite${q.options ? "" : ` (you said ${given})`}.` : "Noted."}
              {answerText(q) && !q.options && <span className="answer"> Answer: <InlineMd text={answerText(q)} />.</span>}
            </p>
            {fig && (
              <p className="evidence happened">
                What happened: the true volatility was {r[Math.min(9, r.length - 1)].toFixed(2)}% ten days after the shock and {r[r.length - 1].toFixed(2)}% after
                {" "}{r.length} days (it was {fig.levels.shock.toFixed(2)}% on the day of the shock, {fig.levels.calm_median.toFixed(2)}% before it).
              </p>
            )}
            <Markdown text={q.explain} className="prose" />
            {fig && q.options && <p className="evidence">{evidence(fig, q.options)}</p>}
            {explored && <p className="small-text">Your first answer is the one kept in your progress.</p>}
            <div className="action-row">
              <button type="button" onClick={() => continueFrom(root.current)} data-testid="predict-continue">Continue</button>
              <button type="button" className="linkish" onClick={tryAgain} data-testid="predict-retry">Try again</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
