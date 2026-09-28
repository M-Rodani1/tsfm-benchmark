import { Link } from "react-router-dom";
import { CopyButton } from "../components/CopyButton";
import { store, useStore } from "../lib/app";
import { lessons, researchStatus } from "../lib/content";
import { dueCards, getProgress, nextLessonStep } from "../lib/progress";
import type { SessionRec } from "../lib/session";
import type { TerminalTask } from "../lib/types";

export function TerminalTaskCard({ task }: { task: TerminalTask }) {
  return (
    <section className="card" data-testid="terminal-task">
      <h2>⌨️ Waiting for you in a terminal: {task.title}</h2>
      <p className="sub">{task.why} Time: {task.minutes}.</p>
      <pre className="cmd">{task.commands.join("\n")}</pre>
      <div className="row">
        <CopyButton text={task.commands.join("\n")} label="Copy commands" />
        <span className="muted">Full instructions: README “Running the real study” and <Link to="/status">Research status</Link>.</span>
      </div>
    </section>
  );
}

export function Home() {
  useStore();
  const now = new Date();
  const plan = nextLessonStep(store);
  const due = dueCards(store, now);
  const done = lessons.filter((l) => getProgress(store, l).status === "completed").length;
  const sessions = store.all<SessionRec>("session_log").sort((a, b) => (a.data.started_at < b.data.started_at ? 1 : -1));
  const today = sessions.filter((s) => new Date(s.data.started_at).toDateString() === now.toDateString());
  const minutesToday = Math.round(today.reduce((n, s) => n + s.data.active_seconds, 0) / 60);
  const reviewMinutes = Math.max(1, Math.round((due.length * 20) / 60));

  return (
    <>
      <h1>Continue</h1>
      <section className="card hero" data-testid="continue">
        {plan ? (
          <>
            <div className="sub">
              {plan.mode === "continue" ? "You stopped in" : "Next up"}: Lesson {plan.lesson.id} · {plan.lesson.title}
            </div>
            <h2 style={{ marginTop: 6 }}>
              Step {plan.stepIndex + 1} of {plan.lesson.steps.length}: {plan.step.title}
            </h2>
            <div className="row">
              <Link className="btn primary" to={`/lessons/${plan.lesson.id}?step=${plan.step.id}`} data-testid="continue-button">
                {plan.mode === "continue" ? "Continue where you stopped" : `Start lesson ${plan.lesson.id}`} →
              </Link>
              <span className="muted">about {plan.minutesLeft} min left in this lesson</span>
            </div>
          </>
        ) : (
          <>
            <h2>All {lessons.length} lessons done 🎉</h2>
            <p>Keep your cards fresh in Review, and follow the research on the Results and Research status pages.</p>
          </>
        )}
      </section>
      <div className="grid2">
        <section className="card" data-testid="due-card">
          <div className="kpi">{due.length}</div>
          <div className="kpi-label">flashcard{due.length === 1 ? "" : "s"} due today</div>
          {due.length > 0 ? (
            <p><Link className="btn" to="/review">Review now (about {reviewMinutes} min)</Link></p>
          ) : (
            <p className="muted">Nothing due. Cards are added when you finish a lesson.</p>
          )}
        </section>
        <section className="card">
          <div className="kpi">{done} / {lessons.length}</div>
          <div className="kpi-label">lessons completed · {minutesToday} min of learning today</div>
          <p><Link to="/lessons">All lessons</Link> · <Link to="/notes">Notes &amp; session log</Link></p>
        </section>
      </div>
      {researchStatus.terminal_tasks.map((t) => <TerminalTaskCard key={t.id} task={t} />)}
      {researchStatus.terminal_tasks.length === 0 && (
        <section className="card"><h2>Research</h2><p>No terminal task is waiting. See <Link to="/results">Results</Link>.</p></section>
      )}
    </>
  );
}
