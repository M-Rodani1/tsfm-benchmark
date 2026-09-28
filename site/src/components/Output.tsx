import { content } from "../lib/content";
import { explainError } from "../lib/errors";
import type { Lesson } from "../lib/types";
import type { PyErrorInfo } from "../py/protocol";
import { InlineMd } from "./Markdown";

export interface CellOutput {
  text: string;
  value?: string | null;
  figures: string[];
  error?: PyErrorInfo;
  earlierFailed?: string;
}

export function ErrorExplanation({ error, lesson, earlierFailed }: { error: PyErrorInfo; lesson: Lesson; earlierFailed?: string }) {
  const ex = explainError(error, lesson.errors, content.errors);
  return (
    <div className="error-box" data-testid="error-box">
      {earlierFailed && <div><strong>An earlier cell of this lesson failed</strong> ({earlierFailed.split(".")[0]}), so this one could not run. Fix or reset that cell first.</div>}
      <div className="etype">{error.type}{error.line ? ` (line ${error.line})` : ""}: {error.message.split("\n")[0].slice(0, 400)}</div>
      {ex ? (
        <div className="explain" data-testid="error-explanation">
          <div><strong>What it means:</strong> <InlineMd text={ex.why} /></div>
          <div><strong>How to fix it:</strong> <InlineMd text={ex.fix} /></div>
        </div>
      ) : (
        <div className="explain">No plain-English explanation for this one yet: read the last line of the message, and check the line number.</div>
      )}
      {error.message.includes("\n") && <pre>{error.message}</pre>}
      {error.traceback && (
        <details><summary>Full traceback</summary><pre>{error.traceback}</pre></details>
      )}
    </div>
  );
}

export function Output({ out, lesson }: { out: CellOutput; lesson: Lesson }) {
  const hasText = out.text || out.value;
  return (
    <>
      {(hasText || out.figures.length > 0) && (
        <div className="output" data-testid="cell-output">
          {out.text}
          {out.value && <div>{out.value}</div>}
          {out.figures.map((f, i) => <img key={i} src={`data:image/png;base64,${f}`} alt={`Figure ${i + 1} produced by this cell`} />)}
        </div>
      )}
      {out.error && <ErrorExplanation error={out.error} lesson={lesson} earlierFailed={out.earlierFailed} />}
    </>
  );
}
