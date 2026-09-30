// A terminal task page (site/content/tasks/<id>.yaml): numbered commands for your OS, each with
// a copy button, what you should see, how long it takes and common errors; then the check of
// the output you paste back (components/TaskCheck.tsx), a self-reported override, and the next step.
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CopyButton } from "../components/CopyButton";
import { Breadcrumb, NextStepButton, PathRail, pathToggleLabel, StatusPill } from "../components/Journey";
import { InlineMd } from "../components/Markdown";
import { Shell } from "../components/Shell";
import { TaskCheck } from "../components/TaskCheck";
import { session, store, useStore } from "../lib/app";
import { content } from "../lib/content";
import { fmtMoment } from "../lib/format";
import type { JourneyRecord } from "../lib/journey";
import { markStarted, useJourney } from "../lib/journeyState";
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
      <span className="cmd-num" aria-hidden="true">{n}</span>
      <div>
        <h3><span className="visually-hidden">Command {n}: </span>{c.title}{c.optional && <span className="opt">optional</span>}</h3>
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
        {c.time && <p className="small-text">Takes {c.time}</p>}
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
      </div>
    </li>
  );
}

export function TaskPage() {
  useStore();
  const { id = "" } = useParams();
  const v = useJourney();
  const task = content.journey.tasks[id];
  const [os, setOs] = useState<Os>(detectOs);
  if (!task)
    return <Shell><div className="content empty"><h1>No such task</h1><p><Link to="/path">Your path</Link></p></div></Shell>;
  const key = `task:${id}`;
  const step = v.phases.flatMap((p) => p.steps).find((s) => s.key === key)!;
  const phase = v.phases.find((p) => p.steps.some((s) => s.key === key))!;
  const rec = store.get<JourneyRecord>("journey_state", key)?.data;
  const running = !step.done && rec?.status === "started";
  const chooseOs = (o: Os) => {
    setOs(o);
    try {
      localStorage.setItem("os", o);
    } catch {
      /* not remembered: fine */
    }
  };
  let n = 0;
  const commands = task.commands.filter((c) => c.os.includes(os));

  return (
    <Shell rail={<PathRail v={v} />} railToggle={pathToggleLabel(v)}>
      <article className="content task" data-testid="task-page" data-task={id}>
        <Breadcrumb stepKey={key} />
        <h1 style={{ marginTop: 6 }}>{task.title}</h1>
        <div className="task-status">
          <StatusPill status={step.status} testId="task-status" running={running} />
          <span>· On your laptop · {task.time}</span>
        </div>
        <p className="lede"><InlineMd text={task.why} /></p>
        {task.note && <p className="next-note" data-testid="task-note">{task.note}</p>}
        {phase.locked && phase.lockReason && step.status === "locked" && (
          <p className="notice" data-testid="task-locked"><span className="label">Not yet.</span> {phase.lockReason} You can read the steps now.</p>
        )}
        {step.done && (
          <p className="notice ok" data-testid="task-done">
            <span className="label">✓ Done</span>{step.method === "output" ? ` — checked from your pasted output (${step.detail})`
              : step.method === "self-reported" ? " — self-reported (not checked)"
              : step.method === "auto" ? " — detected automatically: a real run of the study is published on this site" : ""}.
          </p>
        )}
        {running && (
          <p className="notice info" data-testid="task-started">
            <span className="label">Running since {rec?.started_at ? fmtMoment(rec.started_at) : "you started it"}.</span> Keep learning; paste the output below when it has finished.
          </p>
        )}
        {task.before.length > 0 && (
          <section aria-labelledby="before-title">
            <h2 id="before-title" style={{ marginTop: 32 }}>Before you start</h2>
            <ul className="before">{task.before.map((b, i) => <li key={i}><InlineMd text={b} /></li>)}</ul>
          </section>
        )}
        <div className="segmented" role="tablist" aria-label="Your operating system">
          {(Object.keys(OS_LABEL) as Os[]).map((o) => (
            <button key={o} type="button" role="tab" aria-selected={os === o} onClick={() => chooseOs(o)} data-testid={`os-${o}`}>{OS_LABEL[o]}</button>
          ))}
        </div>
        <ol className="commands" aria-label={`Commands for ${OS_LABEL[os]}`}>
          {commands.map((c) => <Command key={c.title} c={c} n={++n} os={os} />)}
        </ol>
        {task.check.start_button && !step.done && rec?.status !== "started" && (
          <div className="action-row">
            <button type="button" onClick={() => markStarted(store, key, session.id)} data-testid="task-start">{task.check.start_button.replace(/`/g, "")}</button>
            <span className="sub">Marks the study as running, so the site suggests lessons meanwhile.</span>
          </div>
        )}
        <TaskCheck taskId={id} step={step} />
        <NextStepButton next={v.next} here={key} />
      </article>
    </Shell>
  );
}
