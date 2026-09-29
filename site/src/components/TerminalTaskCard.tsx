import { Link } from "react-router-dom";
import type { TerminalTask } from "../lib/types";
import { CopyButton } from "./CopyButton";

export function TerminalTaskCard({ task }: { task: TerminalTask }) {
  return (
    <section className="card" data-testid="terminal-task">
      <h2>⌨️ Waiting for you in a terminal: {task.title}</h2>
      <p className="sub">{task.why} Time: {task.minutes}.</p>
      <pre className="cmd">{task.commands.join("\n")}</pre>
      <div className="row">
        <CopyButton text={task.commands.join("\n")} label="Copy commands" />
        <span className="muted">Step by step, with what you should see and a check of your output: <Link to={task.id === "models" ? "/tasks/setup" : "/tasks/run-study"}>{task.id === "models" ? "Set up your laptop" : "Launch the real study"}</Link> · <Link to="/path">Your path</Link>.</span>
      </div>
    </section>
  );
}
