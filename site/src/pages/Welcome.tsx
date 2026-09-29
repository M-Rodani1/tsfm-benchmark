// The first-visit tour: three short screens from site/content/journey.yaml, skippable, and
// re-openable from the navigation ("Tour"). Finishing or skipping it completes step P0.1.
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { InlineMd, Markdown } from "../components/Markdown";
import { session, store, useStore } from "../lib/app";
import { content } from "../lib/content";
import { markDone } from "../lib/journeyState";
import { Shell } from "../components/Shell";

export function Welcome() {
  useStore();
  const navigate = useNavigate();
  const [i, setI] = useState(0);
  const screens = content.journey.welcome;
  const s = screens[i];
  const finish = (skipped: boolean, to: string) => {
    markDone(store, "site:welcome", "site", skipped ? `tour skipped at screen ${i + 1}` : "tour finished", session.id);
    navigate(to);
  };
  return (
    <Shell>
    <section className="welcome" aria-labelledby="welcome-title" data-testid="welcome" data-screen={i + 1}>
      <div className="row" style={{ marginBottom: 8 }}>
        <span className="kicker" style={{ margin: 0 }}>Welcome · {i + 1} of {screens.length}</span>
        <span className="spacer" />
        <button type="button" className="linkish" onClick={() => finish(true, "/")} data-testid="welcome-skip">Skip the tour</button>
      </div>
      <h1 id="welcome-title">{s.title}</h1>
      <Markdown text={s.body} />
      {i === screens.length - 1 && (
        <ol className="route" data-testid="welcome-route">
          {content.journey.phases.map((p, n) => (
            <li key={p.id}>
              <strong>{n}. {p.title}</strong>{p.kind === "terminal" ? <span className="where"> · on your laptop</span> : null}
              <span className="where"> · {p.time}</span>
              <div className="sub"><InlineMd text={p.goal} /></div>
            </li>
          ))}
        </ol>
      )}
      <div className="stepnav">
        {i < screens.length - 1 ? (
          <button type="button" className="primary" onClick={() => setI(i + 1)} data-testid="welcome-next">Next</button>
        ) : (
          <button type="button" className="primary" onClick={() => finish(false, "/lessons/00")} data-testid="welcome-start">Start lesson 00</button>
        )}
        {i > 0 && <button type="button" onClick={() => setI(i - 1)}>Back</button>}
      </div>
      <p className="small-text" style={{ marginTop: 16 }}>You can open this tour again from <em>Tour</em> under Your path on Home, and see the whole route on <Link to="/path">Your path</Link>.</p>
    </section>
    </Shell>
  );
}
