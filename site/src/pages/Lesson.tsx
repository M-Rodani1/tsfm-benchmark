// A lesson: its steps in the rail (glyph per step, the current one highlighted), one step at a time
// in the main column (serif reading text, figures, exercises), and exactly one primary "Next":
// the next step, or on the last step the next step on your path (nextAction()).
import { useEffect, useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Checkpoint } from "../components/Checkpoint";
import { CodeCell } from "../components/CodeCell";
import { Breadcrumb, NextStepButton, SyntheticBanner } from "../components/Journey";
import { InlineMd, Markdown } from "../components/Markdown";
import { Predict } from "../components/Predict";
import { PyStatus } from "../components/PyStatus";
import { Glyph, Shell } from "../components/Shell";
import { store, useStore } from "../lib/app";
import { content, lessonById } from "../lib/content";
import { useJourney } from "../lib/journeyState";
import { getProgress, missingPrerequisites, overridePrerequisites, percentDone, setCurrentStep, stepDone, type LessonProgress } from "../lib/progress";
import type { Lesson } from "../lib/types";
import { runner } from "../py/runner";

function StepRail({ lesson, progress, stepIndex, goto }: { lesson: Lesson; progress: LessonProgress; stepIndex: number; goto: (i: number) => void }) {
  return (
    <nav aria-label="Steps of this lesson">
      <Breadcrumb stepKey={`lesson:${lesson.id}`} />
      <p className="lesson-rail-title">Lesson {lesson.id}: {lesson.title}</p>
      <ol className="step-list">
        {lesson.steps.map((s, i) => {
          const done = stepDone(s, progress);
          return (
            <li key={s.id}>
              <button type="button" onClick={() => goto(i)} aria-current={i === stepIndex ? "step" : undefined} data-done={done}>
                <Glyph kind={done ? "done" : i === stepIndex ? "current" : "pending"} />
                <span>{s.title}{done && <span className="visually-hidden"> (done)</span>}</span>
              </button>
            </li>
          );
        })}
      </ol>
      <ul className="rail-links">
        <li className="small-text">{percentDone(lesson, progress)}% done · about {lesson.minutes} min in all</li>
        <li><Link to={`/notes?lesson=${lesson.id}`}>My notes for this lesson</Link></li>
      </ul>
    </nav>
  );
}

export function LessonPage() {
  useStore();
  const { id = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const lesson = lessonById(id);
  const journey = useJourney();
  const progress = lesson ? getProgress(store, lesson) : null;
  const requested = params.get("step");
  const stepIndex = useMemo(() => {
    if (!lesson || !progress) return 0;
    const want = requested ?? progress.current_step;
    const i = lesson.steps.findIndex((s) => s.id === want);
    return i >= 0 ? i : 0;
  }, [lesson, progress, requested]);

  const isLocked = !!lesson && !!progress && missingPrerequisites(store, lesson).length > 0 && !progress.prereq_override && progress.status === "not_started";
  useEffect(() => {
    if (lesson && !isLocked) setCurrentStep(store, lesson, lesson.steps[stepIndex].id);
  }, [lesson, stepIndex, isLocked]);

  // start Python in the background as soon as a lesson with code is open
  useEffect(() => {
    if (lesson) void runner.openLesson(lesson).catch(() => {});
  }, [lesson]);

  if (!lesson || !progress)
    return <Shell><div className="content empty"><h1>No such lesson</h1><p><Link to="/lessons">All lessons</Link></p></div></Shell>;
  const step = lesson.steps[stepIndex];
  const missing = missingPrerequisites(store, lesson);
  const locked = missing.length > 0 && !progress.prereq_override && progress.status === "not_started";
  const goto = (i: number) => {
    setParams({ step: lesson.steps[i].id });
    window.scrollTo({ top: 0 });
    requestAnimationFrame(() => document.getElementById("step-title")?.focus({ preventScroll: true }));
  };
  const isLast = stepIndex === lesson.steps.length - 1;
  const needsReal = content.journey.phases.some((p) => p.requires_real_results && p.steps.some((x) => x.key === `lesson:${lesson.id}`));
  const hasPython = step.blocks.some((b) => b.kind === "python" || b.kind === "checkpoint");
  const done = stepDone(step, progress);

  return (
    <Shell rail={<StepRail lesson={lesson} progress={progress} stepIndex={stepIndex} goto={goto} />}
      railToggle={`Lesson ${lesson.id}: step ${stepIndex + 1} of ${lesson.steps.length}`}>
      <div className="content">
        {needsReal && <SyntheticBanner what="this lesson" />}
        {locked ? (
          <section data-testid="prereq-lock" aria-labelledby="lock-title">
            <p className="kicker">Lesson {lesson.id}: {lesson.title}</p>
            <h1 id="lock-title">This lesson builds on lesson{missing.length > 1 ? "s" : ""} {missing.join(", ")}</h1>
            <p className="lede">They are not finished yet. You can go back, or start anyway if you already know the material.</p>
            <div className="action-row">
              <Link className="btn primary" to={`/lessons/${missing[0]}`}>Go to lesson {missing[0]}</Link>
              <button type="button" onClick={() => overridePrerequisites(store, lesson)} data-testid="override">Start anyway</button>
            </div>
          </section>
        ) : (
          // keyed by lesson and step: moving to another lesson never carries over a cell's state
          <article key={`${lesson.id}/${step.id}`} className="step" aria-labelledby="step-title" data-testid="step" data-step={step.id}>
            <div className="step-kicker">
              <span>Step {stepIndex + 1} of {lesson.steps.length}</span>
              {hasPython && <PyStatus />}
            </div>
            <h1 id="step-title" tabIndex={-1}>{step.title}</h1>
            {stepIndex === 0 && (
              <section className="intro" data-testid="lesson-intro" aria-label="About this lesson">
                <h2>You'll be able to</h2>
                <ol>{lesson.objectives.map((o, i) => <li key={i}><InlineMd text={o} /></li>)}</ol>
                <p><strong>You need:</strong> <InlineMd text={lesson.youNeed} /> · About {lesson.minutes} min
                  {lesson.codeToRead.length ? <> · Code you will read: {lesson.codeToRead.map((c, i) => <span key={c}>{i ? ", " : ""}<code>{c}</code></span>)}</> : null}</p>
              </section>
            )}
            {lesson.browserNote && stepIndex === 0 && <p className="callout"><strong>In the browser:</strong> <InlineMd text={lesson.browserNote} /></p>}
            {step.blocks.map((b, i) => {
              if (b.kind === "md") return <Markdown key={i} text={b.text} />;
              if (b.kind === "predict") return <Predict key={b.id} lesson={lesson} block={b} />;
              if (b.kind === "python") return <CodeCell key={b.id} lesson={lesson} block={b} />;
              return <Checkpoint key={b.id} lesson={lesson} />;
            })}
            <div className="stepnav">
              {!isLast && (
                <button type="button" className="primary" onClick={() => goto(stepIndex + 1)} data-testid="next-step" data-next-target>
                  Next: {lesson.steps[stepIndex + 1].title}
                </button>
              )}
              {stepIndex > 0 && <button type="button" onClick={() => goto(stepIndex - 1)}>Back</button>}
              <span className="state">{done ? <span className="verdict-ok">✓ Step done</span> : "Do the activity above to complete this step."}</span>
            </div>
            {isLast && progress.status === "completed" && (
              <p className="lesson-complete verdict-ok" data-testid="lesson-complete">
                Lesson complete. Its {lesson.flashcards.length} flashcards are in your <Link to="/review">review queue</Link>.
              </p>
            )}
            {isLast && <div data-next-target><NextStepButton next={journey.next} here={`lesson:${lesson.id}`} /></div>}
          </article>
        )}
      </div>
    </Shell>
  );
}
