import { useRef, useState } from "react";
import { store, sync, useStore, useSync } from "../lib/app";
import { download } from "../lib/anki";
import { emailAllowed, sendMagicLink, signOut, supabaseConfigured } from "../lib/supabase";
import { Shell } from "../components/Shell";

export function Account() {
  useStore();
  const s = useSync();
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const exportJson = async () => {
    await store.flush();
    const file = store.exportAll();
    download(`tsfm-rc-progress-${file.exported_utc.slice(0, 10)}.json`, JSON.stringify(file, null, 1), "application/json");
    setMsg("Progress exported.");
  };
  const importJson = async (f: File) => {
    try {
      const res = store.importAll(JSON.parse(await f.text()));
      await store.flush();
      setMsg(`Imported: ${res.imported} record(s) restored, ${res.kept} newer local record(s) kept.`);
    } catch (e) {
      setMsg(`Import failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const theme = (() => {
    try {
      return localStorage.getItem("theme") ?? "system";
    } catch {
      return "system";
    }
  })();
  const setTheme = (t: "light" | "dark" | "system") => {
    try {
      if (t === "system") {
        document.documentElement.removeAttribute("data-theme");
        localStorage.removeItem("theme");
      } else {
        document.documentElement.setAttribute("data-theme", t);
        localStorage.setItem("theme", t);
      }
    } catch {
      /* not remembered: applies to this visit */
    }
    setMsg(`Theme: ${t}.`);
  };

  return (
    <Shell>
      <div className="content center">
      <h1>Account</h1>
      <section className="section" data-testid="sync-card" aria-labelledby="where">
        <h2 id="where">Where your progress is saved</h2>
        {(s.mode === "local-only" || s.mode === "signed-out") && (
          <p className="notice" data-testid="local-only-banner"><span className="label">Progress is saved in this browser only: it is not backed up yet.</span>{" "}
            {s.mode === "local-only" ? "Download a copy below now and then." : "Sign in below to back it up."}</p>
        )}
        <p>
          Every change is saved in this browser immediately (IndexedDB), so it survives reloads and works offline.
          {supabaseConfigured
            ? " When you are signed in it is also backed up to your own Supabase database and synced across your devices."
            : " Cloud sync is not configured on this site yet (see docs/DEPLOY.md), so this browser is the only copy: export it regularly."}
        </p>
        {s.mode === "signed-in" && (
          <>
            <p>Signed in as <strong>{s.email}</strong>. {s.syncing ? "Syncing…" : s.lastSyncAt ? `Last sync ${new Date(s.lastSyncAt).toLocaleString()}.` : ""}
              {s.pending ? ` ${s.pending} change(s) waiting.` : ""}</p>
            {s.error && <p className="notice error"><span className="label">Sync failed:</span> {s.error}. Your progress is safe in this browser; try again.</p>}
            <div className="row">
              <button type="button" onClick={() => void sync.syncNow()}>Sync now</button>
              <button type="button" onClick={() => void signOut()}>Sign out</button>
            </div>
          </>
        )}
        {s.mode === "signed-out" && (
          <form className="row" onSubmit={async (e) => {
            e.preventDefault();
            setMsg(null);
            try {
              await sendMagicLink(email);
              setMsg("Check your email for the sign-in link (it opens this site).");
            } catch (err) {
              setMsg(err instanceof Error ? err.message : String(err));
            }
          }}>
            <label className="field">Email
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            </label>
            <button type="submit" className="primary" disabled={!!email && !emailAllowed(email)}>Email me a sign-in link</button>
          </form>
        )}
      </section>
      <section className="section">
        <h2>Export and import</h2>
        <p className="sub">One JSON file with everything: lesson progress, exercise attempts and drafts, notes, flashcard states and review history,
          session log. Importing merges it: for each record the newer version wins.</p>
        <div className="row">
          <button type="button" className="primary" onClick={exportJson} data-testid="export">Download my progress (JSON)</button>
          <button type="button" onClick={() => fileRef.current?.click()} data-testid="import">Restore from a file…</button>
          <input ref={fileRef} type="file" accept="application/json,.json" hidden data-testid="import-file"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) void importJson(f); e.target.value = ""; }} />
        </div>
        {msg && <p role="status" data-testid="account-message">{msg}</p>}
      </section>
      <section className="section">
        <h2>Appearance</h2>
        <div className="segmented" role="radiogroup" aria-label="Theme" style={{ marginTop: 0 }}>
          {(["system", "light", "dark"] as const).map((t) => (
            <button key={t} type="button" role="radio" aria-checked={theme === t} onClick={() => setTheme(t)}
              data-testid={`theme-${t}`}>{t[0].toUpperCase() + t.slice(1)}</button>
          ))}
        </div>
      </section>
      <section className="section">
        <h2>Start over</h2>
        <p className="sub">Deletes the progress stored in this browser (not on the server). Export first if you might want it back.</p>
        <button type="button" onClick={async () => {
          if (window.confirm("Delete all progress stored in this browser?")) {
            await store.resetAll();
            setMsg("Local progress deleted.");
          }
        }}>Delete local progress</button>
      </section>
      </div>
    </Shell>
  );
}
