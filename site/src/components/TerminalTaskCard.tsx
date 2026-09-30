import { Link } from "react-router-dom";
import type { TerminalTask } from "../lib/types";
import { CopyButton } from "./CopyButton";

export function TerminalTaskCard({ task }: { task: TerminalTask }) {
  return (
    <section className="section" data-testid="terminal-task" aria-labelledby={`tt-${task.id}`}>
      <h2 id={`tt-${task.id}`}>Waiting for you in a terminal: {task.title}</h2>
      <p className="sub">{task.why} Time: {task.minutes}.</p>
      <div className="cmd-row">
        <pre className="cmd">{task.commands.join("\n")}</pre>
        <CopyButton text={task.commands.join("\n")} label="Copy" />
      </div>
      <p className="small-text" style={{ marginTop: 8 }}>
        Step by step, with what you should see and a check of your output:{" "}
        <Link to={task.id === "models" ? "/tasks/setup" : "/tasks/run-study"}>{task.id === "models" ? "Set up your laptop" : "Launch the real study"}</Link>
        {" "}· <Link to="/path">Your path</Link>.
      </p>
    </section>
  );
}
