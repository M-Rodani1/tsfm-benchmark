import { useSyncExternalStore } from "react";
import { runner } from "../py/runner";

export function PyStatus() {
  const s = useSyncExternalStore(runner.subscribe, runner.getState);
  return (
    <div className="pystatus" data-testid="py-status" data-stage={s.stage}>
      <span className={`dot ${s.stage}`} aria-hidden="true" />
      <span>{s.text.length > 220 ? s.text.slice(0, 220) + "…" : s.text}</span>
      {(s.stage === "busy" || s.stage === "error" || s.stage === "ready") && (
        <button className="small" type="button" onClick={() => runner.restart()} title="Stops any running code and starts a fresh Python">
          Restart Python
        </button>
      )}
    </div>
  );
}
