import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { store, useStore } from "../lib/app";
import { lessons } from "../lib/content";
import type { SessionRec } from "../lib/session";
import { PathRail, pathToggleLabel } from "../components/Journey";
import { Shell } from "../components/Shell";
import { fmtDuration } from "../lib/format";
import { useJourney } from "../lib/journeyState";

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

export function Notes() {
  useStore();
  const v = useJourney();
  const [params, setParams] = useSearchParams();
  const lessonId = params.get("lesson") ?? lessons[0].id;
  const sessions = store.all<SessionRec>("session_log").sort((a, b) => (a.data.started_at < b.data.started_at ? 1 : -1));
  const total = sessions.reduce((n, s) => n + s.data.active_seconds, 0);
  return (
    <Shell rail={<PathRail v={v} />} railToggle={pathToggleLabel(v)}>
      <div className="content">
      <h1>Notes</h1>
      <section className="section" aria-labelledby="my-notes">
        <div className="section-head" style={{ alignItems: "end", marginBottom: 12 }}>
          <h2 id="my-notes">My notes</h2>
          <label className="field">Lesson
            <select value={lessonId} onChange={(e) => setParams({ lesson: e.target.value })} data-testid="notes-lesson">
              {lessons.map((l) => <option key={l.id} value={l.id}>{l.id} · {l.title}</option>)}
            </select>
          </label>
        </div>
        <NoteEditor key={lessonId} lessonId={lessonId} />
      </section>
      <section className="section" data-testid="session-log" aria-labelledby="history">
        <h2 id="history">Session history</h2>
        <p className="sub">Recorded automatically: active time (tab visible, some input in the last 5 minutes) and what you completed. Total: {fmtDuration(total)}.</p>
        {sessions.length === 0 ? <p className="empty">No sessions yet. They are recorded as you work through lessons.</p> : (
          <div className="tablewrap">
            <table className="stack">
              <thead><tr><th scope="col">Date</th><th scope="col">Time</th><th scope="col">Active</th><th scope="col">Completed</th></tr></thead>
              <tbody>
                {sessions.map((s) => {
                  const d = new Date(s.data.started_at);
                  const done = (s.data.events ?? []).filter((e) => ["step_completed", "lesson_completed", "exercise_passed", "cards_reviewed"].includes(e.type));
                  return (
                    <tr key={s.id}>
                      <td data-label="Date">{d.toLocaleDateString()}</td>
                      <td data-label="Time">{d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</td>
                      <td data-label="Active">{fmtDuration(s.data.active_seconds)}</td>
                      <td data-label="Completed">{done.length ? done.map((e) => `${e.type.replace("_", " ")}: ${e.detail}`).join("; ") : "–"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
      </div>
    </Shell>
  );
}
