import { Link } from "react-router-dom";
import { store, useStore } from "../lib/app";
import { lessons } from "../lib/content";
import { getProgress, missingPrerequisites, percentDone } from "../lib/progress";

export function Lessons() {
  useStore();
  return (
    <>
      <h1>Lessons</h1>
      <p className="sub">
        Eleven sessions of 45–90 minutes. Each teaches the actual code and design of this study, in short steps: a little text,
        then something to do. Python runs in your browser.
      </p>
      <ol className="lesson-list">
        {lessons.map((l) => {
          const p = getProgress(store, l);
          const pct = percentDone(l, p);
          const missing = missingPrerequisites(store, l);
          const locked = missing.length > 0 && !p.prereq_override && p.status === "not_started";
          return (
            <li key={l.id}>
              <Link className="lesson-item" to={`/lessons/${l.id}`} data-testid={`lesson-${l.id}`}>
                <span className="lesson-num">{l.id}</span>
                <span>
                  <strong>{l.title}</strong>
                  <div className="sub">{l.minutes} min · {l.steps.length} steps{l.prerequisites.length ? ` · needs ${l.prerequisites.join(", ")}` : ""}</div>
                </span>
                <span className="row" style={{ justifyContent: "flex-end" }}>
                  {p.status === "completed" ? <span className="status-tag done">✓ done</span>
                    : locked ? <span className="status-tag locked" title={`Finish ${missing.join(", ")} first (you can override)`}>🔒 locked</span>
                    : p.status === "in_progress" ? <span className="progress" aria-label={`${pct}% done`}><span style={{ width: `${pct}%` }} /></span>
                    : <span className="status-tag">not started</span>}
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
      <p className="muted">Offline alternative: the same lessons as Jupyter notebooks in <code>lessons/</code> of the repository.</p>
    </>
  );
}
