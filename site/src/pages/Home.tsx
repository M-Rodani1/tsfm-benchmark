import { Link, Navigate } from "react-router-dom";
import { NextStepCard, StatusPill, StudyRunningCard } from "../components/Journey";
import { store, useStore } from "../lib/app";
import { lessons } from "../lib/content";
import { useJourney } from "../lib/journeyState";
import { dueCards, getProgress } from "../lib/progress";
import type { SessionRec } from "../lib/session";

export function Home() {
  useStore();
  const v = useJourney();
  const now = new Date();
  // first visit: the three-screen tour (re-openable from the menu)
  if (store.ready && v.next.stepKey === "site:welcome" && !store.get("journey_state", "site:welcome")) return <Navigate to="/welcome" replace />;
  const due = dueCards(store, now);
  const done = lessons.filter((l) => getProgress(store, l).status === "completed").length;
  const sessions = store.all<SessionRec>("session_log").sort((a, b) => (a.data.started_at < b.data.started_at ? 1 : -1));
  const today = sessions.filter((s) => new Date(s.data.started_at).toDateString() === now.toDateString());
  const minutesToday = Math.round(today.reduce((n, s) => n + s.data.active_seconds, 0) / 60);
  const reviewMinutes = Math.max(1, Math.round((due.length * 20) / 60));

  return (
    <>
      <h1>Home</h1>
      <NextStepCard next={v.next} />
      {v.studyRunning && <StudyRunningCard />}
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
      <section className="card" data-testid="path-summary">
        <div className="row">
          <h2 style={{ margin: 0 }}>Your path</h2>
          <span className="spacer" />
          <span className="muted">{v.progress.done} of {v.progress.total} steps · {v.progress.percent}%</span>
        </div>
        <ol className="path-mini">
          {v.phases.map((p) => (
            <li key={p.id} data-status={p.status}>
              <Link to={`/path#${p.id}`}>{p.index}. {p.title}</Link>
              {p.kind === "terminal" && <span className="sub"> · ⌨️ on your laptop</span>}
              <span className="spacer" />
              <StatusPill status={p.status} />
            </li>
          ))}
        </ol>
        <p style={{ marginBottom: 0 }}><Link to="/path">See every step →</Link></p>
      </section>
    </>
  );
}
