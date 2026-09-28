import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { store, useStore, useSync } from "../lib/app";
import { dueCards } from "../lib/progress";

function SyncPill() {
  const s = useSync();
  let text: string;
  if (s.mode === "local-only") text = "Saved in this browser";
  else if (s.mode === "signed-out") text = "Not signed in: saved in this browser";
  else if (!s.online) text = `Offline · ${s.pending} change(s) waiting`;
  else if (s.error) text = "Sync error";
  else if (s.syncing) text = "Syncing…";
  else text = s.pending ? `${s.pending} change(s) to sync` : "Synced";
  return <Link to="/account" className="sync-pill" data-testid="sync-pill">{text}</Link>;
}

export function Layout({ children }: { children: ReactNode }) {
  useStore();
  const sync = useSync();
  const due = dueCards(store, new Date()).length;
  const nav = [
    ["/", "Home"], ["/lessons", "Lessons"], ["/review", "Review"], ["/results", "Results"], ["/notes", "Notes & log"], ["/status", "Research status"],
  ] as const;
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand">TSFM Reality Check</Link>
          <nav className="nav" aria-label="Main">
            {nav.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "active" : "")}>
                {label}{to === "/review" && due > 0 && <span className="badge" aria-label={`${due} cards due`}>{due}</span>}
              </NavLink>
            ))}
          </nav>
          <SyncPill />
        </div>
      </header>
      <main id="main">
        {(sync.mode === "local-only" || sync.mode === "signed-out") && (
          <div className="banner warn" data-testid="local-only-banner">
            <strong>Progress is saved in this browser only: it is not backed up yet.</strong>{" "}
            {sync.mode === "local-only"
              ? <>Sync is not configured on this site (see <Link to="/account">Progress &amp; sync</Link>). Use <em>Export</em> there to keep a copy.</>
              : <><Link to="/account">Sign in</Link> to back it up and use it on other devices.</>}
          </div>
        )}
        {!sync.online && <div className="banner info">You are offline. Everything you do is saved here and syncs when you reconnect.</div>}
        {store.lastError && <div className="banner warn">Saving in this browser failed: {store.lastError}</div>}
        {children}
      </main>
    </>
  );
}
