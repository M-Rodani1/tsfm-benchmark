// Automatic session history: date, active time, what was completed (events).
// Active time counts 15-second ticks while the tab is visible and there was input in the
// last 5 minutes. A new session starts after 30 minutes without activity or on a new day.
import type { LocalStore } from "./db";
import type { SessionEvent } from "./progress";

export interface SessionRec { started_at: string; ended_at: string; active_seconds: number; events: SessionEvent[] }

export const TICK_SECONDS = 15;
export const IDLE_MS = 5 * 60_000;
export const NEW_SESSION_MS = 30 * 60_000;

export class SessionTracker {
  id: string | null = null;
  private lastInput = Date.now();
  private timer: ReturnType<typeof setInterval> | null = null;

  constructor(private store: LocalStore, private now: () => Date = () => new Date()) {}

  start() {
    const mark = () => (this.lastInput = this.now().getTime());
    for (const ev of ["pointerdown", "keydown", "scroll", "input"]) window.addEventListener(ev, mark, { passive: true });
    this.ensure();
    this.timer = setInterval(() => this.tick(), TICK_SECONDS * 1000);
  }

  stop() {
    if (this.timer) clearInterval(this.timer);
  }

  /** Current session id, starting a new session if the last one is stale. */
  ensure(): string {
    const now = this.now();
    const cur = this.id ? this.store.get<SessionRec>("session_log", this.id) : undefined;
    const stale = !cur || now.getTime() - Date.parse(cur.data.ended_at) > NEW_SESSION_MS ||
      new Date(cur.data.started_at).toDateString() !== now.toDateString();
    if (stale) {
      this.id = crypto.randomUUID();
      this.store.put<SessionRec>("session_log", this.id, { started_at: now.toISOString(), ended_at: now.toISOString(), active_seconds: 0, events: [] });
    }
    return this.id!;
  }

  tick() {
    const now = this.now();
    const visible = typeof document === "undefined" || document.visibilityState === "visible";
    if (!visible || now.getTime() - this.lastInput > IDLE_MS) return;
    const id = this.ensure();
    const rec = this.store.get<SessionRec>("session_log", id)!;
    this.store.put<SessionRec>("session_log", id, { ...rec.data, ended_at: now.toISOString(), active_seconds: rec.data.active_seconds + TICK_SECONDS });
  }
}
