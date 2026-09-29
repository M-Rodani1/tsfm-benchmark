import { useEffect, useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Checkpoint } from "../components/Checkpoint";
import { CodeCell } from "../components/CodeCell";
import { Breadcrumb, NextStepButton, SyntheticBanner } from "../components/Journey";
import { InlineMd, Markdown } from "../components/Markdown";
import { Predict } from "../components/Predict";
import { PyStatus } from "../components/PyStatus";
import { store, useStore } from "../lib/app";
import { content, lessonById } from "../lib/content";
import { useJourney } from "../lib/journeyState";
import { getProgress, missingPrerequisites, overridePrerequisites, percentDone, setCurrentStep, stepDone } from "../lib/progress";
import { runner } from "../py/runner";

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

  if (!lesson || !progress) return <p>No such lesson. <Link to="/lessons">All lessons</Link></p>;
  const step = lesson.steps[stepIndex];
  const missing = missingPrerequisites(store, lesson);
  const locked = missing.length > 0 && !progress.prereq_override && progress.status === "not_started";
  const goto = (i: number) => {
    setParams({ step: lesson.steps[i].id });
    window.scrollTo({ top: 0 });
  };
  const isLast = stepIndex === lesson.steps.length - 1;
  const needsReal = content.journey.phases.some((p) => p.requires_real_results && p.steps.some((x) => x.key === `lesson:${lesson.id}`));

  return (
    <div className="lesson-layout">
      <aside aria-label="Steps of this lesson">
        <div className="sub">Lesson {lesson.id} · {percentDone(lesson, progress)}% done</div>
        <ol className="steps">
          {lesson.steps.map((s, i) => (
            <li key={s.id}>
              <button type="button" className={i === stepIndex ? "current" : ""} onClick={() => goto(i)} aria-current={i === stepIndex ? "step" : undefined}>
                <span className="tick" aria-hidden="true">{stepDone(s, progress) ? "✓" : `${i + 1}.`}</span>{s.title}
              </button>
            </li>
          ))}
        </ol>
        <p><Link to={`/notes?lesson=${lesson.id}`}>My notes for this lesson</Link></p>
      </aside>
      <div>
        <div className="lesson-head">
          <Breadcrumb stepKey={`lesson:${lesson.id}`} />
          <div className="meta">Lesson {lesson.id} · ⏱ {lesson.minutes} min{lesson.codeToRead.length ? <> · code you will read: {lesson.codeToRead.map((c) => <code key={c} style={{ marginRight: 4 }}>{c}</code>)}</> : null}</div>
          <h1>{lesson.title}</h1>
          {stepIndex === 0 && (
            <div className="card" data-testid="lesson-intro">
              <strong>You'll be able to…</strong>
              <ol>{lesson.objectives.map((o, i) => <li key={i}><InlineMd text={o} /></li>)}</ol>
              <div><strong>You need:</strong> <InlineMd text={lesson.youNeed} /></div>
            </div>
          )}
          {lesson.browserNote && stepIndex === 0 && <div className="callout"><strong>In the browser:</strong> <InlineMd text={lesson.browserNote} /></div>}
          {needsReal && <SyntheticBanner what="this lesson" />}
        </div>
        {locked ? (
          <section className="card" data-testid="prereq-lock">
            <h2>🔒 This lesson builds on lesson{missing.length > 1 ? "s" : ""} {missing.join(", ")}</h2>
            <p>They are not finished yet. You can go back, or start anyway if you already know the material.</p>
            <div className="row">
              <Link className="btn" to={`/lessons/${missing[0]}`}>Go to lesson {missing[0]}</Link>
              <button type="button" onClick={() => overridePrerequisites(store, lesson)} data-testid="override">Start anyway</button>
            </div>
          </section>
        ) : (
          // keyed by lesson and step: moving to another lesson never carries over a cell's state
          <section key={`${lesson.id}/${step.id}`} className="step" aria-labelledby="step-title" data-testid="step" data-step={step.id}>
            <div className="row">
              <span className="sub">Step {stepIndex + 1} of {lesson.steps.length}</span>
              <span className="spacer" />
              <PyStatus />
            </div>
            <h2 id="step-title">{step.title}</h2>
            {step.blocks.map((b, i) => {
              if (b.kind === "md") return <Markdown key={i} text={b.text} />;
              if (b.kind === "predict") return <Predict key={b.id} lesson={lesson} block={b} />;
              if (b.kind === "python") return <CodeCell key={b.id} lesson={lesson} block={b} />;
              return <Checkpoint key={b.id} lesson={lesson} />;
            })}
            <div className="stepnav">
              <button type="button" onClick={() => goto(stepIndex - 1)} disabled={stepIndex === 0}>← Back</button>
              <span className="spacer" />
              {stepDone(step, progress) ? <span className="verdict-ok">✓ step done</span> : <span className="muted">Do the activity above to complete this step</span>}
              {!isLast && <button type="button" className="primary" onClick={() => goto(stepIndex + 1)} data-testid="next-step">Next →</button>}
            </div>
            {isLast && progress.status === "completed" && (
              <p className="verdict-ok" data-testid="lesson-complete">
                Lesson complete. Its {lesson.flashcards.length} flashcards are in your <Link to="/review">review queue</Link>.
              </p>
            )}
            {isLast && <NextStepButton next={journey.next} here={`lesson:${lesson.id}`} />}
          </section>
        )}
      </div>
    </div>
  );
}
