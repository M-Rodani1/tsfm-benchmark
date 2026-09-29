// The 56px top bar: product name, the five sections, whether progress is saved, and the account
// button. Lesson pages show only "Back to Home" (the lesson's own steps are in its rail). Each
// page draws its own body with <Shell> (components/Shell.tsx).
import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { store, useStore, useSync } from "../lib/app";
import { dueCards } from "../lib/progress";

function SyncState() {
  const s = useSync();
  let text: ReactNode;
  let cls = "sync-state";
  if (s.mode === "local-only" || s.mode === "signed-out") text = <>Saved <span className="long">in this browser</span></>;
  else if (!s.online) text = `Offline, ${s.pending} waiting`;
  else if (s.error) { text = "Sync failed"; cls += " error"; }
  else if (s.syncing || s.pending) text = "Saving…";
  else text = "Progress saved";
  return <Link to="/account" className={cls} data-testid="sync-pill" aria-label="Progress and sync settings">{text}</Link>;
}

function AccountButton() {
  const s = useSync();
  const initial = s.mode === "signed-in" && s.email ? s.email[0].toUpperCase() : null;
  return (
    <Link to="/account" className="account-btn" aria-label={initial ? `Account (${s.email})` : "Account"} data-testid="account-button">
      {initial ?? (
        <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
          <circle cx="8" cy="5.5" r="2.75" fill="none" stroke="currentColor" strokeWidth="1.4" />
          <path d="M2.75 14c.6-2.9 2.7-4.4 5.25-4.4s4.65 1.5 5.25 4.4" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      )}
    </Link>
  );
}

const NAV = [["/", "Home"], ["/lessons", "Lessons"], ["/review", "Review"], ["/results", "Results"], ["/notes", "Notes"]] as const;

export function Layout({ children }: { children: ReactNode }) {
  useStore();
  const { pathname } = useLocation();
  const [menu, setMenu] = useState(false);
  useEffect(() => setMenu(false), [pathname]);
  const due = dueCards(store, new Date()).length;
  const inLesson = /^\/lessons\/[^/]+/.test(pathname);
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className={`topbar${menu ? " menu-open" : ""}`}>
        <Link to="/" className="brand">TSFM Reality Check</Link>
        {inLesson ? (
          <nav className="nav lesson-nav" aria-label="Main">
            <Link className="back" to="/">Back to Home</Link>
          </nav>
        ) : (
          <>
            <nav className="nav" id="main-nav" aria-label="Main">
              {NAV.map(([to, label]) => (
                <NavLink key={to} to={to} end={to === "/"}>
                  {label}{to === "/review" && due > 0 && <span className="badge" aria-label={`${due} cards due`}>{due}</span>}
                </NavLink>
              ))}
            </nav>
          </>
        )}
        <div className="topbar-end">
          <SyncState />
          {!inLesson && (
            <button type="button" className="menu-btn" aria-expanded={menu} aria-controls="main-nav" onClick={() => setMenu(!menu)}>
              Menu
            </button>
          )}
          {!inLesson && <AccountButton />}
        </div>
      </header>
      {children}
    </>
  );
}
