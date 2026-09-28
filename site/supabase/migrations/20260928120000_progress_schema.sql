-- TSFM Reality Check: learning-progress storage for ONE user (the site owner).
--
-- Every table:
--   * is keyed by (user_id, id); `id` is chosen by the client (lesson id, card id, uuid ...);
--   * user_id defaults to auth.uid() and must equal it (row-level security, below);
--   * updated_at      = client time of the last change: the last-write-wins key;
--   * server_updated_at = set by the server on every write: the incremental-pull cursor;
--   * deleted         = tombstone, so deletions sync like any other change.
-- Conflict rule (docs/DECISIONS.md D-047): an update whose updated_at is OLDER than the stored
-- row is ignored by the trigger tsfm_lww(), so a stale device can never overwrite a newer
-- change. Append-only tables (exercise_attempts, review_log) use unique ids and never conflict.

create table if not exists public.lesson_progress (
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  id text not null,
  lesson_id text not null,
  status text not null check (status in ('not_started', 'in_progress', 'completed')),
  current_step text,
  completed_steps jsonb not null default '[]'::jsonb,
  activities jsonb not null default '{}'::jsonb,
  prereq_override boolean not null default false,
  started_at timestamptz,
  completed_at timestamptz,
  updated_at timestamptz not null,
  server_updated_at timestamptz not null default now(),
  deleted boolean not null default false,
  primary key (user_id, id)
);

create table if not exists public.exercise_attempts (
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  id text not null,
  lesson_id text not null,
  exercise_id text not null,
  code text not null,
  passed boolean not null,
  hints_used integer not null default 0,
  solution_viewed boolean not null default false,
  error text,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  server_updated_at timestamptz not null default now(),
  deleted boolean not null default false,
  primary key (user_id, id)
);

create table if not exists public.exercise_drafts (
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  id text not null,
  lesson_id text not null,
  cell_id text not null,
  code text not null,
  hints_revealed integer not null default 0,
  solution_viewed boolean not null default false,
  updated_at timestamptz not null,
  server_updated_at timestamptz not null default now(),
  deleted boolean not null default false,
  primary key (user_id, id)
);

create table if not exists public.notes (
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  id text not null,
  lesson_id text not null,
  body text not null default '',
  updated_at timestamptz not null,
  server_updated_at timestamptz not null default now(),
  deleted boolean not null default false,
  primary key (user_id, id)
);

create table if not exists public.flashcard_state (
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  id text not null,
  card_id text not null,
  lesson_id text not null,
  ease real not null,
  interval_days real not null,
  repetitions integer not null,
  lapses integer not null default 0,
  due date not null,
  last_reviewed timestamptz,
  updated_at timestamptz not null,
  server_updated_at timestamptz not null default now(),
  deleted boolean not null default false,
  primary key (user_id, id)
);

create table if not exists public.review_log (
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  id text not null,
  card_id text not null,
  grade integer not null check (grade between 0 and 3),
  reviewed_at timestamptz not null,
  interval_before real,
  interval_after real,
  ease_before real,
  ease_after real,
  updated_at timestamptz not null,
  server_updated_at timestamptz not null default now(),
  deleted boolean not null default false,
  primary key (user_id, id)
);

create table if not exists public.session_log (
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  id text not null,
  started_at timestamptz not null,
  ended_at timestamptz not null,
  active_seconds integer not null default 0,
  events jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null,
  server_updated_at timestamptz not null default now(),
  deleted boolean not null default false,
  primary key (user_id, id)
);

-- last-write-wins + server cursor
create or replace function public.tsfm_lww() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'UPDATE' and new.updated_at < old.updated_at then
    return null;  -- keep the newer stored row: an older client write never wins
  end if;
  new.server_updated_at := clock_timestamp();
  return new;
end;
$$;

do $$
declare
  t text;
begin
  foreach t in array array['lesson_progress', 'exercise_attempts', 'exercise_drafts', 'notes', 'flashcard_state', 'review_log', 'session_log']
  loop
    execute format('drop trigger if exists tsfm_lww on public.%I', t);
    execute format('create trigger tsfm_lww before insert or update on public.%I for each row execute function public.tsfm_lww()', t);
    execute format('create index if not exists %I on public.%I (user_id, server_updated_at)', t || '_pull_idx', t);

    -- Row-level security: a signed-in user reads and writes only their own rows;
    -- the anonymous role gets nothing at all.
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on public.%I from anon', t);
    execute format('grant select, insert, update, delete on public.%I to authenticated', t);
    execute format('drop policy if exists own_rows_select on public.%I', t);
    execute format('drop policy if exists own_rows_insert on public.%I', t);
    execute format('drop policy if exists own_rows_update on public.%I', t);
    execute format('drop policy if exists own_rows_delete on public.%I', t);
    execute format('create policy own_rows_select on public.%I for select to authenticated using ((select auth.uid()) = user_id)', t);
    execute format('create policy own_rows_insert on public.%I for insert to authenticated with check ((select auth.uid()) = user_id)', t);
    execute format('create policy own_rows_update on public.%I for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id)', t);
    execute format('create policy own_rows_delete on public.%I for delete to authenticated using ((select auth.uid()) = user_id)', t);
  end loop;
end;
$$;
