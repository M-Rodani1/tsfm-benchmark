# Deploying the website (Netlify + Supabase)

The website in `site/` is a static single-page app. Netlify builds and hosts it. Your
progress is always saved in your browser first; Supabase (free tier) adds a login and a
Postgres backup, so the same progress follows you across devices. Without Supabase the site
still works in **local-only mode**, with a banner saying progress is not backed up.

Allow about 30 minutes. You need a GitHub account with this repository, a Netlify account and
a Supabase account (both have free tiers), and access to the DNS settings of your domain.

---

## 1. Create the Supabase project (about 5 minutes)

1. Go to <https://supabase.com/dashboard> and sign in. Click **New project**.
2. Pick your organisation, a **Name** (e.g. `tsfm-progress`), a strong **Database password**
   (store it in your password manager; the site never needs it) and a **Region** close to you.
   Click **Create new project** and wait until it is ready.
3. Open **Project Settings → API** (in some dashboard versions: **Project Settings → API Keys**).
   Copy two values into a temporary note:
   - **Project URL**, e.g. `https://abcdefghijkl.supabase.co`;
   - the **public** key: the one labelled `anon` `public` or **Publishable key**
     (starts with `eyJ…` or `sb_publishable_…`).

   **Never copy the `service_role` / secret key anywhere.** The site does not need it. The
   build refuses to run if you paste it by mistake (`site/scripts/env.mjs`).

## 2. Create the tables and the security rules (about 3 minutes)

1. In the Supabase dashboard open **SQL Editor → New query**.
2. Open `site/supabase/migrations/20260928120000_progress_schema.sql` from this repository,
   copy the **whole file**, paste it into the editor and click **Run**. It should finish with
   "Success. No rows returned".
3. Check the result: open **Table Editor**. You should see eight tables (`lesson_progress`,
   `exercise_attempts`, `exercise_drafts`, `notes`, `flashcard_state`, `review_log`,
   `session_log`, `journey_state`), and none of them should carry a red "RLS disabled" /
   "Unrestricted" badge. Under **Authentication → Policies** each table has four policies
   (`own_rows_*`).

   Running the file twice is safe. **If you set up Supabase before the guided journey was
   added** (seven tables, no `journey_state`), run the whole file again: it adds the new
   table with the same protection and leaves your data alone. If you prefer the Supabase CLI:
   `supabase link --project-ref <ref>` and then `supabase db push` from `site/`.

## 3. Set up login for one user (about 3 minutes)

1. **Authentication → Sign In / Providers → Email**: make sure **Email** is enabled. Magic
   links are the default; the site only sends magic links (no passwords).
2. **Authentication → URL Configuration**:
   - **Site URL**: your final address, e.g. `https://tsfm.example.com` (set it again in
     step 6 if you only know the `*.netlify.app` address for now);
   - **Redirect URLs**: add `https://tsfm.example.com/**` and your
     `https://<your-site>.netlify.app/**`.
3. Sign in once from the deployed site (step 5), then come back here and turn off
   **Authentication → Sign In / Providers → Allow new users to sign up**. From then on nobody
   else can create an account. Row-level security already ensures that any other account
   could only ever see its own rows, never yours.

## 4. Connect the repository to Netlify (about 5 minutes)

1. Go to <https://app.netlify.com>, click **Add new site → Import an existing project →
   GitHub**, and authorise Netlify for the repository `M-Rodani1/tsfm-benchmark`.
2. Choose the branch **`main`**. Netlify reads `netlify.toml` from the repository root:
   base directory `site`, build command `npm run build`, publish directory `site/dist`
   (shown as `dist` relative to the base). Leave these fields as they are.
3. Before the first deploy, open **Site configuration → Environment variables → Add a
   variable** and add:

   | Key | Value | Scopes |
   |---|---|---|
   | `VITE_SUPABASE_URL` | the Project URL from step 1 | Builds |
   | `VITE_SUPABASE_ANON_KEY` | the **public** anon/publishable key from step 1 | Builds |
   | `VITE_ALLOWED_EMAIL` | your email address (optional; the login form accepts only it) | Builds |

   These values end up in the public JavaScript. That is by design for the anon key:
   row-level security protects the data, not the key. `.env.example` in `site/` lists the
   same names for local development (`cp site/.env.example site/.env.local`).
4. Click **Deploy site**. The first build takes 2–4 minutes. A red build log saying
   `service_role` or `secret key` means the wrong key was pasted in step 4.3; fix it and
   click **Deploys → Trigger deploy**.

## 5. First visit and first sign-in

1. Open the `https://<random-name>.netlify.app` address Netlify shows. The first visit starts
   a three-screen tour (skip it or go through it; *Tour* in the menu opens it again).
2. The yellow banner says progress is saved in this browser only. Click **Progress & sync**,
   enter your email and click **Email me a sign-in link**. Open the link from the email on the
   same device: the banner disappears and the top-right shows **Synced**.
3. Now go back to step 3.3 and disable new sign-ups.

The first time you run lesson code the browser downloads Python and its scientific packages
(about 40 MB from `cdn.jsdelivr.net`). After that they are cached, and the site and its
lessons also work offline.

## 6. Use your own subdomain (about 5 minutes + DNS propagation)

1. In Netlify: **Domain management → Add a domain → Add a domain you already own**, type the
   subdomain, e.g. `tsfm.example.com`, click **Verify**, then **Add subdomain**.
2. Netlify shows the DNS record to create. In your DNS provider (where `example.com` is
   managed), add:

   | Type | Name / Host | Value / Target | TTL |
   |---|---|---|---|
   | `CNAME` | `tsfm` | `<your-site>.netlify.app` | Auto (or 3600) |

   Do not add an `A` record for the subdomain, and remove any existing record named `tsfm`.
3. Wait until Netlify shows the domain as verified (minutes to a few hours). Under
   **Domain management → HTTPS** click **Verify DNS configuration** and then
   **Provision certificate**. HTTPS is then automatic.
4. Back in Supabase (step 3.2), make sure **Site URL** is `https://tsfm.example.com` and the
   redirect list contains `https://tsfm.example.com/**`.

## 7. Keeping it up to date

- **New results.** After `make reproduce` on your computer, run `make publish-results`,
  then `git add site/public/data/results`, `git commit` and `git push` (Phase 5 on the site
  walks you through it). Netlify rebuilds automatically. Once the site shows a published
  real run of the study (`default`, not synthetic), it marks phases 1, 2 and 5 of **Your
  path** as done by itself and unlocks phases 6–7.
- **Lesson edits.** Edit `site/content/…`, run `make lessons` (regenerates the notebooks) and
  `make test`, then commit and push.
- **Backups.** Besides Supabase, **Progress & sync → Download my progress (JSON)** saves
  everything in one file; **Restore from a file…** merges it back (the newer version of
  each record wins).

## How the site guides you

The site is built around a guided journey (`site/content/journey.yaml`): eight phases from a
short tour to a published, audited study.

- **What to do next.** Home always shows one *Do this next* card. **Your path** shows every
  phase and step.
- **Terminal steps.** Steps done on your laptop have pages with the commands for macOS,
  Windows (WSL) or Linux, what you should see, and a box that checks the output you paste
  back. Only a short summary of the check is stored, never the pasted text.
- **Where it is saved.** Journey state is stored and synced like the rest of your progress
  (table `journey_state`).
- **Nothing to configure.** The journey needs no settings beyond the Supabase and Netlify
  steps above.

## Security notes

- Every table has row-level security: a signed-in user reads and writes only rows whose
  `user_id` is their own; the anonymous role has no access. `site/tests/rls.test.ts` checks
  this against a real Postgres on every CI run.
- The site sends strict security headers (`netlify.toml`): a Content-Security-Policy that
  allows scripts only from the site itself (plus WebAssembly), network access only to the
  site, Supabase and the Pyodide package CDN, and `frame-ancestors 'none'`.
- No raw price data is published: the site holds derived result tables and the committed
  **synthetic** fixtures used by the lessons.
