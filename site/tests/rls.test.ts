// The Supabase migrations, applied to a real Postgres (PGlite, in-process) with a minimal
// stand-in for Supabase's auth schema: RLS is enabled on every table, users only ever see and
// change their own rows, the anonymous role has no access, and last-write-wins holds.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { PGlite } from "@electric-sql/pglite";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { TABLES } from "../src/lib/db";

const MIG = join(__dirname, "..", "supabase", "migrations");
const A = "11111111-1111-4111-8111-111111111111";
const B = "22222222-2222-4222-8222-222222222222";

const SAMPLE: Record<string, Record<string, unknown>> = {
  lesson_progress: { lesson_id: "01", status: "in_progress", current_step: "x", updated_at: "2026-01-01T00:00:00Z" },
  exercise_attempts: { lesson_id: "01", exercise_id: "f", code: "x", passed: true, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
  exercise_drafts: { lesson_id: "01", cell_id: "c", code: "x", updated_at: "2026-01-01T00:00:00Z" },
  notes: { lesson_id: "01", body: "hello", updated_at: "2026-01-01T00:00:00Z" },
  flashcard_state: { card_id: "01-1", lesson_id: "01", ease: 2.5, interval_days: 1, repetitions: 1, due: "2026-01-02", updated_at: "2026-01-01T00:00:00Z" },
  review_log: { card_id: "01-1", grade: 2, reviewed_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
  session_log: { started_at: "2026-01-01T00:00:00Z", ended_at: "2026-01-01T00:10:00Z", updated_at: "2026-01-01T00:00:00Z" },
  journey_state: { step_key: "task:setup", status: "done", method: "output", detail: "27 checks", done_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
};

let db: PGlite;

async function as(role: "authenticated" | "anon" | "postgres", sub: string | null, fn: () => Promise<void>) {
  await db.exec(`reset role; select set_config('request.jwt.claim.sub', '${sub ?? ""}', false);`);
  if (role !== "postgres") await db.exec(`set role ${role}`);
  try {
    await fn();
  } finally {
    await db.exec("reset role");
  }
}

function insertSql(table: string, id: string, extra: Record<string, unknown> = {}) {
  const row: Record<string, unknown> = { id, ...SAMPLE[table], ...extra };
  const cols = Object.keys(row);
  const vals = cols.map((c) => (row[c] === null ? "null" : `'${String(row[c]).replace(/'/g, "''")}'`));
  return `insert into public.${table} (${cols.join(", ")}) values (${vals.join(", ")})`;
}

beforeAll(async () => {
  db = new PGlite();
  await db.exec(`
    create schema auth;
    create table auth.users (id uuid primary key);
    create function auth.uid() returns uuid language sql stable
      as $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
    create role anon nologin;
    create role authenticated nologin;
    grant usage on schema public to anon, authenticated;
    grant usage on schema auth to anon, authenticated;
    grant execute on function auth.uid() to anon, authenticated;
    insert into auth.users values ('${A}'), ('${B}');
  `);
  for (const f of readdirSync(MIG).filter((n) => n.endsWith(".sql")).sort()) await db.exec(readFileSync(join(MIG, f), "utf8"));
}, 60_000);

afterAll(async () => db?.close());

describe("Supabase schema and row-level security", () => {
  it("has exactly the client's tables, each with RLS enabled and four own-row policies", async () => {
    const t = await db.query<{ relname: string; relrowsecurity: boolean }>(
      "select c.relname, c.relrowsecurity from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and c.relkind = 'r' order by 1");
    expect(t.rows.map((r) => r.relname).sort()).toEqual([...TABLES].sort());
    for (const r of t.rows) expect(r.relrowsecurity, r.relname).toBe(true);
    const p = await db.query<{ tablename: string; n: number }>("select tablename, count(*)::int as n from pg_policies where schemaname = 'public' group by 1");
    for (const r of p.rows) expect(r.n, r.tablename).toBe(4);
    expect(p.rows.length).toBe(TABLES.length);
  });

  it("isolates users: B can neither read, change nor delete A's rows, nor write rows as A", async () => {
    await as("authenticated", A, async () => {
      for (const t of TABLES) await db.exec(insertSql(t, `a-${t}`));
    });
    await as("authenticated", B, async () => {
      for (const t of TABLES) {
        expect((await db.query(`select * from public.${t}`)).rows.length, t).toBe(0);
        expect((await db.query(`update public.${t} set deleted = true`)).affectedRows ?? 0, t).toBe(0);
        expect((await db.query(`delete from public.${t}`)).affectedRows ?? 0, t).toBe(0);
        await expect(db.exec(insertSql(t, `b-as-a-${t}`, { user_id: A })), t).rejects.toThrow(/row-level security/);
      }
    });
    await as("authenticated", A, async () => {
      for (const t of TABLES) {
        const rows = (await db.query<{ user_id: string; deleted: boolean }>(`select user_id, deleted from public.${t}`)).rows;
        expect(rows.length, t).toBe(1);
        expect(rows[0].user_id).toBe(A); // user_id defaulted to auth.uid()
        expect(rows[0].deleted).toBe(false);
      }
    });
  });

  it("protects the journey table exactly like the others (same four policies, same grants)", async () => {
    const policies = async (t: string) =>
      (await db.query<{ policyname: string; cmd: string; roles: string; qual: string | null; with_check: string | null }>(
        `select policyname, cmd, roles::text, qual, with_check from pg_policies where schemaname = 'public' and tablename = '${t}' order by policyname`)).rows;
    expect(await policies("journey_state")).toEqual(await policies("lesson_progress"));
    const grants = async (t: string) =>
      (await db.query<{ grantee: string; privilege_type: string }>(
        `select grantee, privilege_type from information_schema.role_table_grants where table_schema = 'public' and table_name = '${t}' and grantee in ('anon', 'authenticated') order by 1, 2`)).rows;
    expect(await grants("journey_state")).toEqual(await grants("lesson_progress"));
    await as("authenticated", A, async () => {
      await expect(db.exec(insertSql("journey_state", "bad-status", { status: "maybe" }))).rejects.toThrow(/check constraint/);
      await expect(db.exec(insertSql("journey_state", "bad-method", { method: "guess" }))).rejects.toThrow(/check constraint/);
    });
  });

  it("can be run again on a project that already has data (how an existing project gets journey_state)", async () => {
    const count = async () => (await db.query<{ n: number }>("select count(*)::int as n from public.lesson_progress")).rows[0].n;
    const before = await count();
    expect(before).toBeGreaterThan(0); // rows written by the tests above
    for (const f of readdirSync(MIG).filter((n) => n.endsWith(".sql")).sort()) await db.exec(readFileSync(join(MIG, f), "utf8"));
    expect(await count()).toBe(before);
    const p = await db.query<{ tablename: string; n: number }>("select tablename, count(*)::int as n from pg_policies where schemaname = 'public' group by 1");
    expect(p.rows.length).toBe(TABLES.length);
    for (const r of p.rows) expect(r.n, r.tablename).toBe(4);
  });

  it("gives the anonymous role no access at all", async () => {
    await as("anon", null, async () => {
      for (const t of TABLES) await expect(db.query(`select * from public.${t}`), t).rejects.toThrow(/permission denied/);
    });
  });

  it("applies last-write-wins by updated_at and advances the server cursor", async () => {
    await as("authenticated", A, async () => {
      const read = async () => (await db.query<{ body: string; server_updated_at: string }>(
        "select body, server_updated_at::text from public.notes where id = 'lww'")).rows[0];
      await db.exec(insertSql("notes", "lww", { body: "v2", updated_at: "2026-02-02T00:00:00Z" }));
      const first = await read();
      const upsert = (body: string, at: string) =>
        db.exec(`insert into public.notes (id, lesson_id, body, updated_at) values ('lww', '01', '${body}', '${at}')
                 on conflict (user_id, id) do update set body = excluded.body, updated_at = excluded.updated_at`);
      await upsert("stale", "2026-02-01T00:00:00Z"); // older client write: ignored
      expect((await read()).body).toBe("v2");
      await upsert("v3", "2026-02-03T00:00:00Z"); // newer: wins
      const after = await read();
      expect(after.body).toBe("v3");
      expect(after.server_updated_at > first.server_updated_at).toBe(true);
    });
  });
});

describe("upgrading a project set up before the guided journey", () => {
  it("running the current migration on the old seven-table schema adds journey_state, protected, and keeps the data", async () => {
    const MIGFILE = join(MIG, "20260928120000_progress_schema.sql");
    const current = readFileSync(MIGFILE, "utf8");
    // the schema as committed before the journey (3f02ef0): the same file without the journey parts
    const old = current.slice(0, current.indexOf("-- The guided journey")) +
      current.slice(current.indexOf("-- last-write-wins + server cursor")).replace(", 'journey_state']", "]");
    expect(old).not.toContain("journey_state");
    const pg = new PGlite();
    await pg.exec(`
      create schema auth; create table auth.users (id uuid primary key);
      create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
      create role anon nologin; create role authenticated nologin;
      grant usage on schema public to anon, authenticated; grant usage on schema auth to anon, authenticated;
      grant execute on function auth.uid() to anon, authenticated;
      insert into auth.users values ('${A}');`);
    await pg.exec(old);
    await pg.exec(`insert into public.notes (user_id, id, lesson_id, body, updated_at) values ('${A}', 'n1', '01', 'kept', '2026-01-01T00:00:00Z')`);
    await pg.exec(current);
    const tables = (await pg.query<{ relname: string; relrowsecurity: boolean }>(
      "select c.relname, c.relrowsecurity from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and c.relkind = 'r'")).rows;
    expect(tables.map((r) => r.relname).sort()).toEqual([...TABLES].sort());
    expect(tables.every((r) => r.relrowsecurity)).toBe(true);
    const policies = (await pg.query<{ n: number }>("select count(*)::int as n from pg_policies where tablename = 'journey_state'")).rows[0].n;
    expect(policies).toBe(4);
    expect((await pg.query<{ body: string }>("select body from public.notes where id = 'n1'")).rows[0].body).toBe("kept");
    await pg.close();
  }, 60_000);
});
