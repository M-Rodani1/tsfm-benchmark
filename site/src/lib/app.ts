// Singletons shared by the whole app: the local store, the session log and the sync manager.
import { useSyncExternalStore } from "react";
import type { Session } from "@supabase/supabase-js";
import { IdbBackend, LocalStore, TABLES, type Table } from "./db";
import { SessionTracker } from "./session";
import { currentSession, onAuthChange, supabase, supabaseConfigured, SupabaseRemote } from "./supabase";
import { syncOnce, type CursorStore } from "./sync";

export const store = new LocalStore(new IdbBackend());
export const session = new SessionTracker(store);

export type SyncMode = "local-only" | "signed-out" | "signed-in";
export interface SyncState {
  mode: SyncMode;
  email: string | null;
  syncing: boolean;
  lastSyncAt: string | null;
  error: string | null;
  online: boolean;
  pending: number;
}

class SyncManager {
  state: SyncState = { mode: supabaseConfigured ? "signed-out" : "local-only", email: null, syncing: false, lastSyncAt: null,
    error: null, online: typeof navigator === "undefined" ? true : navigator.onLine, pending: 0 };
  private listeners = new Set<() => void>();
  private session: Session | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;

  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };
  getState = () => this.state;
  private set(p: Partial<SyncState>) {
    this.state = { ...this.state, ...p };
    for (const fn of this.listeners) fn();
  }

  private cursors: CursorStore = {
    get: async (t: Table) => (await store.backend.getMeta<string>(`cursor:${t}`)) ?? null,
    set: async (t: Table, v: string) => store.backend.setMeta(`cursor:${t}`, v),
  };

  async start() {
    window.addEventListener("online", () => { this.set({ online: true }); this.schedule(0); });
    window.addEventListener("offline", () => this.set({ online: false }));
    store.subscribe(() => {
      const pending = store.countDirty();
      if (pending !== this.state.pending) this.set({ pending });
      if (pending) this.schedule(2000);
    });
    this.set({ pending: store.countDirty() });
    if (!supabaseConfigured) return;
    await this.onSession(await currentSession());
    onAuthChange((s) => void this.onSession(s));
    setInterval(() => this.schedule(0), 60_000);
  }

  private async onSession(s: Session | null) {
    this.session = s;
    if (!s) {
      this.set({ mode: "signed-out", email: null });
      return;
    }
    const prevUser = await store.backend.getMeta<string>("user_id");
    if (prevUser !== s.user.id) {
      // first sign-in on this device (or a different account): push everything made here
      await store.backend.setMeta("user_id", s.user.id);
      for (const t of TABLES) await store.backend.setMeta(`cursor:${t}`, null);
      store.markAllDirty();
    }
    this.set({ mode: "signed-in", email: s.user.email ?? null });
    this.schedule(0);
  }

  schedule(ms: number) {
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => void this.syncNow(), ms);
  }

  async syncNow() {
    const sb = supabase();
    if (!sb || !this.session || !navigator.onLine || this.state.syncing) return;
    this.set({ syncing: true, error: null });
    try {
      await syncOnce(store, new SupabaseRemote(sb, this.session.user.id), this.cursors);
      this.set({ syncing: false, lastSyncAt: new Date().toISOString(), pending: store.countDirty() });
    } catch (e) {
      this.set({ syncing: false, error: e instanceof Error ? e.message : String(e) });
    }
  }
}

export const sync = new SyncManager();

export function useStore() {
  useSyncExternalStore(store.subscribe, store.getVersion);
  return store;
}

export function useSync() {
  return useSyncExternalStore(sync.subscribe, sync.getState);
}
