import { Link } from "react-router-dom";
import { PathRail, pathToggleLabel } from "../components/Journey";
import { Glyph, Shell } from "../components/Shell";
import { store, useStore } from "../lib/app";
import { lessons } from "../lib/content";
import { useJourney } from "../lib/journeyState";
import { getProgress, missingPrerequisites, percentDone } from "../lib/progress";

export function Lessons() {
  useStore();
  const v = useJourney();
  return (
    <Shell rail={<PathRail v={v} />} railToggle={pathToggleLabel(v)}>
      <div className="content">
        <h1>Lessons</h1>
        <p className="lede">
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
                    <span className="t">{l.title}</span>
                    <span className="small-text" style={{ display: "block" }}>
                      {l.minutes} min · {l.steps.length} steps{l.prerequisites.length ? ` · builds on ${l.prerequisites.join(", ")}` : ""}
                    </span>
                  </span>
                  <span className="status-word" data-status={p.status}>
                    {p.status === "completed" ? <><Glyph kind="done" />done</>
                      : p.status === "in_progress" ? <><span className="progress" aria-hidden="true"><span style={{ width: `${pct}%` }} /></span>{pct}% done</>
                      : locked ? <><Glyph kind="pending" />after {missing.join(", ")}</>
                      : <><Glyph kind="pending" />not started</>}
                  </span>
                </Link>
              </li>
            );
          })}
        </ol>
        <p className="small-text">Offline alternative: the same lessons as Jupyter notebooks in <code>lessons/</code> of the repository.</p>
      </div>
    </Shell>
  );
}
