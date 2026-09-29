// The study-console shell: a 290px white rail next to the grey main column. Below 860px the
// rail becomes a disclosure button above the main column (one copy of the DOM, no duplicate).
// Status glyphs and the notices shown on every page live here too. Layout rules: site/DESIGN.md.
import { useId, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { store, sync, useSync } from "../lib/app";

export type GlyphKind = "done" | "running" | "current" | "pending";

/** A 16px status mark. Decorative: the status is always also written next to it. */
export function Glyph({ kind }: { kind: GlyphKind }) {
  return (
    <svg className={`glyph ${kind}`} viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      {kind === "done" && (
        <>
          <circle className="fill-done" cx="8" cy="8" r="7.5" />
          <path className="check" d="M4.6 8.2 7 10.5l4.4-4.8" fill="none" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </>
      )}
      {kind === "running" && <circle className="ring-blue" cx="8" cy="8" r="6.5" fill="none" strokeWidth="1.6" strokeDasharray="3 2.1" />}
      {kind === "current" && (
        <>
          <circle className="ring-blue" cx="8" cy="8" r="6.5" fill="none" strokeWidth="1.6" />
          <circle className="dot-blue" cx="8" cy="8" r="3" />
        </>
      )}
      {kind === "pending" && <circle className="ring-pending" cx="8" cy="8" r="6.5" fill="none" strokeWidth="1.5" />}
    </svg>
  );
}

/** Problems shown above every page: a failed sync (with a retry), offline, a failed save. Where
 * progress lives when there is no problem is on Home (Today) and Account, not on every page. */
export function Notices() {
  const s = useSync();
  return (
    <>
      {s.mode === "signed-in" && s.online && s.error && (
        <div className="notice error" role="alert" data-testid="sync-error">
          <span className="label">Sync failed.</span> Your progress is safe in this browser{s.pending ? ` (${s.pending} change${s.pending === 1 ? "" : "s"} waiting)` : ""};
          it has not reached your account yet. <span className="sub">{s.error}</span>{" "}
          <button type="button" className="small" onClick={() => void sync.syncNow()} data-testid="sync-retry">Try again</button>
        </div>
      )}
      {!s.online && (
        <div className="notice info" data-testid="offline-banner">
          <span className="label">You are offline.</span> Everything you do is saved here and syncs when you reconnect.
        </div>
      )}
      {store.lastError && (
        <div className="notice error" role="alert" data-testid="store-error">
          <span className="label">Saving in this browser failed:</span> {store.lastError}. Reload the page; if it keeps failing,
          export your progress from <Link to="/account">Account</Link>.
        </div>
      )}
    </>
  );
}

export function Shell({ rail, railToggle, children, testId }: {
  rail?: ReactNode;
  /** The disclosure label below 860px, e.g. "Your path: Phase 3 of 8, Foundations". */
  railToggle?: ReactNode;
  children: ReactNode;
  testId?: string;
}) {
  const [open, setOpen] = useState(false);
  const bodyId = useId();
  return (
    <div className={`shell${rail ? "" : " no-rail"}`} data-testid={testId}>
      {rail && (
        <aside className={`rail${open ? " open" : ""}`} aria-label="Navigation for this page">
          <div className="rail-inner">
            <button type="button" className="rail-toggle" aria-expanded={open} aria-controls={bodyId} onClick={() => setOpen(!open)}
              data-testid="rail-toggle">
              <span>{railToggle}</span>
              <svg className="chev" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M2 4.5 6 8l4-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>
            </button>
            <div className="rail-body" id={bodyId}>{rail}</div>
          </div>
        </aside>
      )}
      <main id="main" className="main" tabIndex={-1}>
        <Notices />
        {children}
      </main>
    </div>
  );
}

export function Loading({ text }: { text: string }) {
  return <p className="loading" role="status"><span className="dot" aria-hidden="true" />{text}</p>;
}
