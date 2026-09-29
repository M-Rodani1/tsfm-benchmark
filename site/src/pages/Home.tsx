// Home, the study console: the one next action, the study running on your laptop and how the site
// knows each part of it, the models under test (from study.json, never typed by hand), and Today.
import { useRef } from "react";
import { Link, Navigate } from "react-router-dom";
import { PathRail, pathToggleLabel } from "../components/Journey";
import { InlineMd } from "../components/Markdown";
import { Shell } from "../components/Shell";
import { TaskCheck } from "../components/TaskCheck";
import { store, useStore, useSync } from "../lib/app";
import { lessonById, lessons, researchStatus } from "../lib/content";
import { capitalise, fmtDate, fmtDuration, fmtMoment, numberWord } from "../lib/format";
import type { JourneyRecord, JourneyView, NextAction, StepView } from "../lib/journey";
import { realResultsPublished, useJourney } from "../lib/journeyState";
import { dueCards, getProgress, lessonPlan } from "../lib/progress";
import type { SessionRec } from "../lib/session";

/** The context line and H1 of the next action (presentation of nextAction(), which decides it). */
function headline(next: NextAction, v: JourneyView): { context: string; title: string } {
  if (next.kind === "done") return { context: "Your path is complete", title: next.title };
  const phase = v.phases.find((p) => p.id === next.phaseId);
  const where = phase ? `Phase ${phase.index} · ${phase.title}` : "";
  if (next.kind === "lesson" && phase && next.stepKey) {
    const L = lessonById(next.stepKey.slice("lesson:".length));
    if (L) {
      const plan = lessonPlan(store, L);
      if (getProgress(store, L).status === "in_progress" && plan.step)
        return { context: `${where} · lesson ${L.id}, step ${plan.stepIndex + 1} of ${L.steps.length}`, title: `Next: ${plan.step.title}` };
      const inPhase = phase.steps.filter((s) => s.kind === "lesson" && !s.optional);
      return { context: `${where} · lesson ${inPhase.findIndex((s) => s.key === next.stepKey) + 1} of ${inPhase.length}`, title: `Next: ${L.title}` };
    }
  }
  return { context: `${where}${phase?.kind === "terminal" ? " · on your laptop" : ""}`, title: `Next: ${next.title}` };
}

function NextActionBlock({ v }: { v: JourneyView }) {
  const next = v.next;
  const h = headline(next, v);
  return (
    <section className="next-action" data-testid="next-action" data-step={next.stepKey ?? "done"} aria-labelledby="next-title">
      <p className="kicker" data-testid="next-action-context">{h.context}</p>
      <h1 id="next-title" data-testid="next-action-title"><InlineMd text={h.title} /></h1>
      <p className="lede"><InlineMd text={next.why} /></p>
      {next.note && <p className="next-note" data-testid="next-action-note">{next.note}</p>}
      <div className="action-row">
        <Link className="btn primary" to={next.to} data-testid="next-action-button">{next.button}</Link>
        {next.minutes && <span className="time">{capitalise(next.minutes)}</span>}
      </div>
      {next.alternative && (
        <p className="next-alt"><Link to={next.alternative.to} data-testid="next-action-alternative">{next.alternative.label}</Link></p>
      )}
    </section>
  );
}

type Row = { stage: string; produces: string; status: string; tone: "done" | "running" | "waiting"; how: string };

const HOW_METHOD = { output: "Verified from output", "self-reported": "Self-reported", auto: "Detected: a real run is published on this site", site: "" } as const;

/** Each stage of `make reproduce`: what it makes, where it stands, and how the site knows. The site
 * cannot see your laptop, so a running study is only ever self-reported; a finished one is
 * verified from the output you paste, or detected once its results are published. */
function studyRows(run: StepView, publish: StepView, rec: JourneyRecord | undefined): Row[] {
  const S = researchStatus.study;
  const years = S ? `${S.data.start.slice(0, 4)} to ${S.data.end.slice(0, 4)}` : "";
  const produces = [
    ["Data", S ? `Daily prices for ${S.data.tickers} tickers, ${years}` : "Daily prices for the pre-registered tickers"],
    ["Baselines", S ? `${capitalise(numberWord(S.baselines.length))} classical forecasters, from a zero forecast and AR up to GARCH, HAR and LightGBM` : "The classical forecasters"],
    ["Foundation models", `Zero-shot forecasts from the ${S ? numberWord(S.models.length) : ""} models below`.replace("  ", " ")],
    ["Statistics", S ? `${S.primary_tests} pre-registered primary tests, plus the secondary tables` : "The pre-registered tests"],
  ];
  const tickers = /(\d+) tickers/.exec(run.detail)?.[1];
  const models = /(\d+)\/(\d+) models available/.exec(run.detail);
  const detail: Record<string, string> = {
    Data: tickers ? `: ${tickers} tickers loaded` : "",
    "Foundation models": models ? `: ${models[1]} of ${models[2]} available` : "",
  };
  const rows: Row[] = produces.map(([stage, what]) => {
    if (run.done) {
      const how = run.method === "output" ? `${HOW_METHOD.output}${detail[stage] ?? ""}` : HOW_METHOD[run.method ?? "site"];
      return { stage, produces: what, status: "Done", tone: "done", how };
    }
    if (rec?.status === "started") return { stage, produces: what, status: "Running", tone: "running", how: "Self-reported: you started it" };
    return { stage, produces: what, status: "Not started", tone: "waiting", how: "Not yet" };
  });
  rows.push({
    stage: "Publish", produces: "Results on this site, replacing the synthetic ones",
    status: publish.done ? "Done" : run.done ? "Next" : "Waiting", tone: publish.done ? "done" : "waiting",
    how: publish.done ? HOW_METHOD[publish.method ?? "site"] || "Done" : "Not yet",
  });
  return rows;
}

/** Rows spanned by a cell starting at row i (0 if the row above already covers it). */
function span(rows: Row[], i: number, key: (r: Row) => string): number {
  if (i > 0 && key(rows[i - 1]) === key(rows[i])) return 0;
  let n = 1;
  while (i + n < rows.length && key(rows[i + n]) === key(rows[i])) n++;
  return n;
}

function StudySection({ v }: { v: JourneyView }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const steps = v.phases.flatMap((p) => p.steps);
  const run = steps.find((s) => s.key === "task:run-study")!;
  const publish = steps.find((s) => s.key === "task:publish")!;
  const rec = store.get<JourneyRecord>("journey_state", "task:run-study")?.data;
  const rows = studyRows(run, publish, rec);
  const meta = run.done ? `finished${rec?.done_at ? ` ${fmtMoment(rec.done_at)}` : ""}`
    : rec?.status === "started" ? `started ${rec.started_at ? fmtMoment(rec.started_at) : ""}` : "not started";
  return (
    <section className="section" aria-labelledby="study-title" data-testid="study-table">
      <div className="section-head">
        <h2 id="study-title">The study on your laptop</h2>
        <span className="meta"><code>make reproduce</code>, {meta}</span>
      </div>
      {v.studyRunning && (
        <p className="sub" data-testid="study-running">Keep going with lessons. Come back here when it finishes; the site cannot see your laptop, so until then it only knows what you told it.</p>
      )}
      <table className="stack study">
        <thead><tr><th scope="col">Stage</th><th scope="col">What it produces</th><th scope="col">Status</th><th scope="col">How we know</th></tr></thead>
        <tbody>
          {rows.map((r, i) => {
            // One fact about several stages (they run as one command) is shown once, spanning them.
            // Stacked into label/value rows on a phone, each row shows it again instead (CSS
            // shows one of the two copies, so assistive technology meets it once either way).
            const status = span(rows, i, (x) => x.status);
            const how = span(rows, i, (x) => x.how);
            const grouped = (key: (x: Row) => string) => (i > 0 && key(rows[i - 1]) === key(r)) || (i + 1 < rows.length && key(rows[i + 1]) === key(r));
            const statusCell = <span className={`status-${r.tone}`}>{r.status}</span>;
            return (
              <tr key={r.stage} data-testid={`study-${r.stage.toLowerCase().replace(/ /g, "-")}`} data-status={r.status}>
                <th scope="row">{r.stage}</th>
                <td data-label="What it produces">{r.produces}</td>
                {status > 0 && <td data-label="Status" rowSpan={status} className={status > 1 ? "merged" : undefined}>{statusCell}</td>}
                {grouped((x) => x.status) && <td data-label="Status" className="per-row">{statusCell}</td>}
                {how > 0 && <td data-label="How we know" rowSpan={how} className={how > 1 ? "merged" : undefined}>{r.how}</td>}
                {grouped((x) => x.how) && <td data-label="How we know" className="per-row">{r.how}</td>}
              </tr>
            );
          })}
        </tbody>
      </table>
      {v.studyRunning ? (
        <div className="section-foot">
          <button type="button" onClick={() => dialog.current?.showModal()} data-testid="study-finished" aria-describedby="finished-how">It has finished</button>
          <span className="sub" id="finished-how">You will paste the last lines of its output to confirm.</span>
        </div>
      ) : !run.done ? (
        <div className="section-foot">
          <Link className="btn" to="/tasks/run-study">How to start it</Link>
          <span className="sub">About 15 minutes of your time, then several hours on its own.</span>
        </div>
      ) : null}
      <dialog ref={dialog} className="sheet" aria-labelledby="finished-title" data-testid="finished-dialog">
        <div className="sheet-head">
          <h2 id="finished-title">Has the study finished?</h2>
          <button type="button" className="small" onClick={() => dialog.current?.close()}>Close</button>
        </div>
        <div className="sheet-body">
          <TaskCheck taskId="run-study" step={run} allowSelfReport={false} allowReset={false} headingLevel={3} />
        </div>
      </dialog>
    </section>
  );
}

function ModelsSection() {
  const S = researchStatus.study;
  return (
    <section className="section" aria-labelledby="models-title" data-testid="models-under-test">
      <div className="section-head"><h2 id="models-title">Models under test</h2></div>
      {!S ? (
        <p className="empty">The model list is written by <code>make publish-results</code>; it is missing from this build.</p>
      ) : (
        <>
          <table className="stack">
            <thead><tr><th scope="col">Model</th><th scope="col">Weights released</th><th scope="col">Clean test data from</th></tr></thead>
            <tbody>
              {S.models.map((m) => (
                <tr key={m.name}>
                  <th scope="row">{m.label}</th>
                  <td data-label="Weights released"><time dateTime={m.effective_release}>{fmtDate(m.effective_release)}</time></td>
                  <td data-label="Clean test data from"><time dateTime={m.clean_start}>{fmtDate(m.clean_start)}</time></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="small-text" style={{ marginTop: 12 }}>
            Clean test data start {S.buffer_days} days after a model's weights were released, so no test day can be in its training data
            (from <code>{S.config}</code>).{" "}
            {S.weights_dates_from ? "Release dates include the weights' commit dates your run recorded."
              : "Until your run records the weights' commit dates, these are the documented release dates."}
          </p>
        </>
      )}
    </section>
  );
}

function Today() {
  const now = new Date();
  const due = dueCards(store, now).length;
  const done = lessons.filter((l) => getProgress(store, l).status === "completed").length;
  const seconds = store.all<SessionRec>("session_log").reduce((n, s) => n + s.data.active_seconds, 0);
  const real = realResultsPublished();
  const sync = useSync();
  return (
    <aside className="today" aria-labelledby="today-title">
      <h2 id="today-title">Today</h2>
      <div className="today-item" data-testid="due-card">
        <p><span className="num">{due}</span> flashcard{due === 1 ? "" : "s"} due</p>
        {due > 0
          ? <p><Link to="/review">Review, about {Math.max(1, Math.round((due * 20) / 60))} minute{Math.round((due * 20) / 60) > 1 ? "s" : ""}</Link></p>
          : <p className="small-text">Cards join when you finish a lesson.</p>}
      </div>
      <div className="today-item">
        <p><span className="num">{done} of {lessons.length}</span> lessons done</p>
        <p className="small-text">{fmtDuration(seconds)} of learning so far</p>
      </div>
      <div className="today-item" data-testid="results-state">
        {real ? (
          <><p>Results on this site are from your run</p><p className="small-text"><Link to="/results">Open Results</Link></p></>
        ) : (
          <><p>Results on this site are synthetic</p><p className="small-text">They switch to your real numbers when you publish.</p></>
        )}
      </div>
      {(sync.mode === "local-only" || sync.mode === "signed-out") && (
        <div className="today-item" data-testid="local-only-banner">
          <p>Progress is saved in this browser only</p>
          <p className="small-text">{sync.mode === "local-only"
            ? <>Sync is not set up on this site. <Link to="/account">Export a copy</Link> now and then.</>
            : <><Link to="/account">Sign in</Link> to back it up and use it on other devices.</>}</p>
        </div>
      )}
    </aside>
  );
}

export function Home() {
  useStore();
  const v = useJourney();
  // first visit: the three-screen tour (re-openable from the rail)
  if (store.ready && v.next.stepKey === "site:welcome" && !store.get("journey_state", "site:welcome")) return <Navigate to="/welcome" replace />;
  return (
    <Shell rail={<PathRail v={v} />} railToggle={pathToggleLabel(v)}>
      <div className="home-cols">
        <div>
          <NextActionBlock v={v} />
          <StudySection v={v} />
          <ModelsSection />
        </div>
        <Today />
      </div>
    </Shell>
  );
}
