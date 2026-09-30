// Supabase: magic-link login for one user, Postgres storage behind row-level security.
// Only the public anon/publishable key is used (VITE_SUPABASE_ANON_KEY); the build refuses a
// secret key (scripts/env.mjs). Without both variables the site runs in local-only mode.
import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";
import type { Table } from "./db";
import type { Remote, RemoteRow } from "./sync";

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;
export const allowedEmail = ((import.meta.env.VITE_ALLOWED_EMAIL as string | undefined) ?? "").trim().toLowerCase();

export const supabaseConfigured = Boolean(url && anonKey);

let client: SupabaseClient | null = null;
export function supabase(): SupabaseClient | null {
  if (!supabaseConfigured) return null;
  client ??= createClient(url!, anonKey!, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: "pkce" },
  });
  return client;
}

export function emailAllowed(email: string): boolean {
  return !allowedEmail || email.trim().toLowerCase() === allowedEmail;
}

export async function sendMagicLink(email: string): Promise<void> {
  const sb = supabase();
  if (!sb) throw new Error("Sync is not configured on this site.");
  if (!emailAllowed(email)) throw new Error("This site is set up for a single user; that email is not allowed.");
  const { error } = await sb.auth.signInWithOtp({ email: email.trim(), options: { emailRedirectTo: window.location.origin + "/account" } });
  if (error) throw error;
}

export async function signOut() {
  await supabase()?.auth.signOut();
}

export async function currentSession(): Promise<Session | null> {
  const sb = supabase();
  if (!sb) return null;
  const { data } = await sb.auth.getSession();
  return data.session;
}

export function onAuthChange(fn: (s: Session | null) => void): () => void {
  const sb = supabase();
  if (!sb) return () => {};
  const { data } = sb.auth.onAuthStateChange((_evt, s) => fn(s));
  return () => data.subscription.unsubscribe();
}

export class SupabaseRemote implements Remote {
  constructor(private sb: SupabaseClient, private userId: string) {}

  async push(table: Table, rows: RemoteRow[]) {
    const { error } = await this.sb.from(table).upsert(rows.map((r) => ({ ...r, user_id: this.userId })), { onConflict: "user_id,id" });
    if (error) throw new Error(`${table}: ${error.message}`);
  }

  async pull(table: Table, since: string | null) {
    let q = this.sb.from(table).select("*").order("server_updated_at", { ascending: true }).limit(5000);
    if (since) q = q.gt("server_updated_at", since);
    const { data, error } = await q;
    if (error) throw new Error(`${table}: ${error.message}`);
    return (data ?? []) as RemoteRow[];
  }
}
