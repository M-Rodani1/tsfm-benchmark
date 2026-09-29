import { useSyncExternalStore } from "react";
import { runner } from "../py/runner";

/** Python in this browser: loading, ready, busy, or failed (with a way to recover). */
export function PyStatus() {
  const s = useSyncExternalStore(runner.subscribe, runner.getState);
  return (
    <span className="pystatus" data-testid="py-status" data-stage={s.stage} role="status">
      <span className={`dot ${s.stage}`} aria-hidden="true" />
      <span>{s.text.length > 220 ? s.text.slice(0, 220) + "…" : s.text}</span>
      {(s.stage === "busy" || s.stage === "error" || s.stage === "ready") && (
        <button className="small" type="button" onClick={() => runner.restart()} title="Stops any running code and starts a fresh Python">
          {s.stage === "error" ? "Try again" : "Restart Python"}
        </button>
      )}
    </span>
  );
}
