import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { store, useStore } from "../lib/app";
import { lessons } from "../lib/content";
import type { SessionRec } from "../lib/session";

function NoteEditor({ lessonId }: { lessonId: string }) {
  const [text, setText] = useState(() => store.get<{ body: string }>("notes", lessonId)?.data.body ?? "");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pending = useRef<string | null>(null);
  const save = () => {
    if (pending.current === null) return;
    store.put("notes", lessonId, { lesson_id: lessonId, body: pending.current });
    pending.current = null;
  };
  useEffect(() => {
    window.addEventListener("pagehide", save);
    return () => {
      save();
      window.removeEventListener("pagehide", save);
    };
  });
  return (
    <textarea className="notes" aria-label={`Notes for lesson ${lessonId}`} data-testid="notes" value={text} placeholder="What would you forget? Write it here (saved as you type)."
      onChange={(e) => {
        setText(e.target.value);
        pending.current = e.target.value;
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(save, 400);
      }} />
  );
}

function fmtDuration(s: number) {
  const m = Math.round(s / 60);
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

export function Notes() {
  useStore();
  const [params, setParams] = useSearchParams();
  const lessonId = params.get("lesson") ?? lessons[0].id;
  const sessions = store.all<SessionRec>("session_log").sort((a, b) => (a.data.started_at < b.data.started_at ? 1 : -1));
  const total = sessions.reduce((n, s) => n + s.data.active_seconds, 0);
  return (
    <>
      <h1>Notes &amp; log</h1>
      <section className="card">
        <div className="row">
          <h2 style={{ margin: 0 }}>My notes</h2>
          <label className="field">Lesson
            <select value={lessonId} onChange={(e) => setParams({ lesson: e.target.value })} data-testid="notes-lesson">
              {lessons.map((l) => <option key={l.id} value={l.id}>{l.id} · {l.title}</option>)}
            </select>
          </label>
        </div>
        <NoteEditor key={lessonId} lessonId={lessonId} />
      </section>
      <section className="card" data-testid="session-log">
        <h2>Session history</h2>
        <p className="sub">Recorded automatically: active time (tab visible, some input in the last 5 minutes) and what you completed. Total: {fmtDuration(total)}.</p>
        {sessions.length === 0 ? <p className="muted">No sessions yet.</p> : (
          <div className="tablewrap">
            <table>
              <thead><tr><th>Date</th><th>Time</th><th>Active</th><th>Completed</th></tr></thead>
              <tbody>
                {sessions.map((s) => {
                  const d = new Date(s.data.started_at);
                  const done = (s.data.events ?? []).filter((e) => ["step_completed", "lesson_completed", "exercise_passed", "cards_reviewed"].includes(e.type));
                  return (
                    <tr key={s.id}>
                      <td>{d.toLocaleDateString()}</td>
                      <td>{d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</td>
                      <td>{fmtDuration(s.data.active_seconds)}</td>
                      <td>{done.length ? done.map((e) => `${e.type.replace("_", " ")}: ${e.detail}`).join("; ") : "–"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
