// A terminal task page (site/content/tasks/<id>.yaml): numbered commands for your OS, each with
// a copy button, what you should see, how long it takes and common errors; then the check of
// the output you paste back (lib/cliparse.ts), a self-reported override, and the next step.
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CopyButton } from "../components/CopyButton";
import { Breadcrumb, NextStepButton, StatusPill } from "../components/Journey";
import { InlineMd } from "../components/Markdown";
import { CHECKERS, type CheckResult } from "../lib/cliparse";
import { session, store, useStore } from "../lib/app";
import { content } from "../lib/content";
import type { JourneyRecord } from "../lib/journey";
import { markDone, markStarted, resetStep, useJourney } from "../lib/journeyState";
import type { Os, TaskCommand } from "../lib/types";

const OS_LABEL: Record<Os, string> = { macos: "macOS", windows: "Windows (WSL)", linux: "Linux" };

function detectOs(): Os {
  try {
    const saved = localStorage.getItem("os");
    if (saved === "macos" || saved === "windows" || saved === "linux") return saved;
  } catch {
    /* storage blocked: fall through */
  }
  const ua = typeof navigator === "undefined" ? "" : navigator.userAgent;
  return /Mac/i.test(ua) ? "macos" : /Win/i.test(ua) ? "windows" : "linux";
}

function Command({ c, n, os }: { c: TaskCommand; n: number; os: Os }) {
  const run = c.run ?? c.run_os?.[os] ?? null;
  return (
    <li className="command" data-testid="task-command">
      <h3><span className="cmd-num">{n}</span> {c.title}{c.optional && <span className="status-tag optional">optional</span>}</h3>
      {c.where && <p className="sub">Run it in: {c.where}</p>}
      {run && (
        <div className="cmd-row">
          <pre className="cmd">{run}</pre>
          <CopyButton text={run} />
        </div>
      )}
      {c.text && <p><InlineMd text={c.text} /></p>}
      {c.os_note?.[os] && <p className="callout"><InlineMd text={c.os_note[os]!} /></p>}
      {c.expect && <p><strong>What you should see:</strong> <InlineMd text={c.expect} /></p>}
      {c.time && <p className="sub">⏱ {c.time}</p>}
      {c.errors.length > 0 && (
        <details className="errors">
          <summary>Common problems ({c.errors.length})</summary>
          <ul>
            {c.errors.map((e, i) => (
              <li key={i}>
                <code>{e.see}</code>
                <div><InlineMd text={e.fix} />{e.source !== "task" && <span className="sub"> (from {e.source === "make doctor" ? "`make doctor`" : "errors.yaml"})</span>}</div>
              </li>
            ))}
          </ul>
        </details>
      )}
    </li>
  );
}

export function TaskPage() {
  useStore();
  const { id = "" } = useParams();
  const v = useJourney();
  const task = content.journey.tasks[id];
  const [os, setOs] = useState<Os>(detectOs);
  const [text, setText] = useState("");
  const [result, setResult] = useState<CheckResult | null>(null);
  if (!task) return <p>No such task. <Link to="/path">Your path</Link></p>;
  const key = `task:${id}`;
  const step = v.phases.flatMap((p) => p.steps).find((s) => s.key === key)!;
  const phase = v.phases.find((p) => p.steps.some((s) => s.key === key))!;
  const rec = store.get<JourneyRecord>("journey_state", key)?.data;
  const chooseOs = (o: Os) => {
    setOs(o);
    try {
      localStorage.setItem("os", o);
    } catch {
      /* not remembered: fine */
    }
  };
  const check = () => {
    const r = CHECKERS[task.check.parser](text, content.errors);
    setResult(r);
    if (r.verdict === "success") markDone(store, key, "output", r.detail, session.id);
    else if (r.verdict === "partial" && task.long_running) markStarted(store, key, session.id);
  };
  const selfReport = () => {
    if (!window.confirm("Mark this step as done without a checked output? It will be shown as self-reported.")) return;
    markDone(store, key, "self-reported", "self-reported", session.id);
  };
  let n = 0;
  const commands = task.commands.filter((c) => c.os.includes(os));

  return (
    <article className="task" data-testid="task-page" data-task={id}>
      <Breadcrumb stepKey={key} />
      <div className="row">
        <h1 style={{ margin: "4px 0" }}>⌨️ {task.title}</h1>
        <span className="spacer" />
        <StatusPill status={step.status} testId="task-status" />
      </div>
      <p className="why"><InlineMd text={task.why} /></p>
      {task.note && <p className="banner info" data-testid="task-note"><strong>{task.note}</strong></p>}
      <p className="sub">⏱ {task.time}</p>
      {phase.locked && phase.lockReason && step.status === "locked" && (
        <p className="banner warn" data-testid="task-locked">🔒 {phase.lockReason} You can read the steps now.</p>
      )}
      {step.done && (
        <p className="banner ok-banner" data-testid="task-done">
          ✓ Done{step.method === "output" ? ` — checked from your pasted output (${step.detail})`
            : step.method === "self-reported" ? " — self-reported (not checked)"
            : step.method === "auto" ? " — detected automatically: a real run of the study is published on this site" : ""}.
        </p>
      )}
      {!step.done && rec?.status === "started" && (
        <p className="banner info" data-testid="task-started">⏳ Started {rec.started_at ? new Date(rec.started_at).toLocaleString() : ""}. Keep learning; paste the output below when it has finished.</p>
      )}
      {task.before.length > 0 && (
        <section className="card">
          <h2>Before you start</h2>
          <ul>{task.before.map((b, i) => <li key={i}><InlineMd text={b} /></li>)}</ul>
        </section>
      )}
      <div className="os-tabs" role="tablist" aria-label="Your operating system">
        {(Object.keys(OS_LABEL) as Os[]).map((o) => (
          <button key={o} type="button" role="tab" aria-selected={os === o} className={os === o ? "current" : ""} onClick={() => chooseOs(o)}
            data-testid={`os-${o}`}>{OS_LABEL[o]}</button>
        ))}
      </div>
      <ol className="commands">
        {commands.map((c) => <Command key={c.title} c={c} n={++n} os={os} />)}
      </ol>
      {task.check.start_button && !step.done && rec?.status !== "started" && (
        <p><button type="button" onClick={() => markStarted(store, key, session.id)} data-testid="task-start">⏳ {task.check.start_button.replace(/`/g, "")}</button>
          <span className="sub"> Marks the study as running, so the site suggests lessons meanwhile.</span></p>
      )}
      <section className="card check" id="check" data-testid="task-check">
        <h2>Check the output</h2>
        <p><InlineMd text={task.check.prompt} /></p>
        <p className="sub">Success looks like: <InlineMd text={task.check.success} /> Only this summary is stored, never the text you paste.</p>
        <textarea className="code" rows={8} value={text} onChange={(e) => setText(e.target.value)} spellCheck={false}
          placeholder="Paste the terminal output here" aria-label="Pasted terminal output" data-testid="task-output" />
        <div className="row">
          <button type="button" className="primary" onClick={check} disabled={!text.trim()} data-testid="task-check-button">Check</button>
          {!step.done && <button type="button" className="small" onClick={selfReport} data-testid="task-self-report">I've done this (self-reported)</button>}
          {rec && step.method !== "auto" && (
            <button type="button" className="small" onClick={() => { resetStep(store, key); setResult(null); }} data-testid="task-reset">Reset this step</button>
          )}
        </div>
        {result && (
          <div className={`check-result ${result.verdict}`} data-testid="task-result" data-verdict={result.verdict} role="status">
            <strong>{result.verdict === "success" ? "✓ " : result.verdict === "failure" ? "✗ " : result.verdict === "partial" ? "… " : "? "}
              <InlineMd text={result.summary} /></strong>
            {result.problems.length > 0 && (
              <ul>
                {result.problems.map((p, i) => (
                  <li key={i}>
                    <InlineMd text={p.title} />{p.detail && <div className="sub"><InlineMd text={p.detail} /></div>}
                    {p.fix && <div>→ <InlineMd text={p.fix} /></div>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>
      <NextStepButton next={v.next} here={key} />
    </article>
  );
}
