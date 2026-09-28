// Compile site/content (the single source of the lessons) into src/generated/content.json.
//
// Mirrors lessons/_tools/content.py (the Python parser that generates the Jupyter track);
// tests/test_lessons.py and site/tests/content.test.ts check that both agree and enforce the
// same rules. Format: site/content/README.md.
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { load as yamlLoad } from "js-yaml";

export const PROSE_LIMIT = 150;
export const LESSON_PROSE_LIMIT = 650;
const BLOCK_KINDS = new Set(["python", "predict", "checkpoint"]);
const FENCE_OPEN = /^```([A-Za-z0-9_-]*)\s*$/;

export function slugify(text) {
  const s = text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return s || "step";
}

/** Words of prose: inline code counts as one word (same rule as content.py). */
export function words(text) {
  const t = text.replace(/`[^`]*`/g, " x ");
  return (t.match(/[A-Za-z0-9][A-Za-z0-9'’-]*/g) ?? []).length;
}

export function splitFrontMatter(text) {
  if (!text.startsWith("---\n")) throw new Error("lesson.md must start with YAML front matter (---)");
  const end = text.indexOf("\n---\n", 4);
  return { meta: yamlLoad(text.slice(4, end)) ?? {}, body: text.slice(end + 5) };
}

export function parseBody(body) {
  const lines = body.split("\n");
  const steps = [];
  const intro = [];
  let md = [];
  const flush = () => {
    const text = md.join("\n").trim();
    md = [];
    if (!text) return;
    if (steps.length) steps[steps.length - 1].blocks.push({ kind: "md", text });
    else intro.push(text);
  };
  for (let i = 0; i < lines.length; ) {
    const line = lines[i];
    const m = FENCE_OPEN.exec(line);
    if (m && BLOCK_KINDS.has(m[1])) {
      let j = i + 1;
      while (j < lines.length && lines[j].trimEnd() !== "```") j++;
      if (j === lines.length) throw new Error(`unclosed \`\`\` ${m[1]} block at line ${i + 1}`);
      const content = lines.slice(i + 1, j).join("\n");
      flush();
      if (!steps.length) throw new Error(`\`\`\` ${m[1]} block before the first step`);
      const block = { kind: m[1], text: m[1] === "predict" ? content : content.replace(/\n+$/, "") };
      if (m[1] === "predict") block.data = yamlLoad(content) ?? {};
      steps[steps.length - 1].blocks.push(block);
      i = j + 1;
      continue;
    }
    if (m && m[1]) {
      let j = i + 1;
      while (j < lines.length && lines[j].trimEnd() !== "```") j++;
      md.push(...lines.slice(i, j + 1));
      i = j + 1;
      continue;
    }
    if (line.startsWith("## ")) {
      flush();
      steps.push({ title: line.slice(3).trim(), blocks: [] });
    } else md.push(line);
    i++;
  }
  flush();
  return { intro: intro.join("\n\n"), steps };
}

export function proseSegments(step) {
  const segs = [];
  let cur = [];
  for (const b of step.blocks) {
    if (b.kind === "md") cur.push(b.text);
    else {
      segs.push(cur.join("\n\n"));
      cur = [];
    }
  }
  segs.push(cur.join("\n\n"));
  return segs;
}

/** Files the browser writes under TSFM_RC_ROOT for a lesson (mirror of run_content.mount_files). */
export function mountFiles(mounts, repo, resultsIndex) {
  const out = [];
  for (const m of mounts ?? []) {
    if (m === "fixtures") {
      for (const f of ["synthetic_ohlcv.csv", "synthetic_latent.csv", "MANIFEST.json"])
        out.push({ path: `data/fixtures/${f}`, url: `/data/fixtures/${f}` });
    } else if (m === "configs") {
      for (const f of readdirSync(join(repo, "configs")).filter((n) => n.endsWith(".yaml")).sort())
        out.push({ path: `configs/${f}`, url: `/data/configs/${f}` });
    } else if (m.startsWith("results:")) {
      const run = m.split(":")[1];
      const entry = resultsIndex.runs.find((r) => r.run === run);
      if (!entry) throw new Error(`mount ${m}: run not published (make publish-results)`);
      out.push({ path: "site/public/data/results/index.json", url: "/data/results/index.json" });
      for (const rel of [...Object.values(entry.tables), entry.report])
        out.push({ path: `site/public/data/results/${rel}`, url: `/data/results/${rel}` });
    } else throw new Error(`unknown mount ${m}`);
  }
  return out;
}

function loadYaml(p) {
  return yamlLoad(readFileSync(p, "utf8"));
}

export function loadLesson(dir, slug, repo, resultsIndex) {
  const { meta, body } = splitFrontMatter(readFileSync(join(dir, "lesson.md"), "utf8"));
  const { intro, steps: raw } = parseBody(body);
  if (intro) throw new Error(`${slug}: text before the first step`);
  const cp = join(dir, "checkpoint");
  const ex = loadYaml(join(cp, "exercise.yaml"));
  const lesson = {
    id: String(meta.id),
    slug,
    title: meta.title,
    minutes: meta.minutes,
    objectives: meta.objectives ?? [],
    prerequisites: meta.prerequisites ?? [],
    youNeed: meta.you_need ?? "",
    codeToRead: meta.code_to_read ?? [],
    browserNote: meta.browser_note ?? null,
    next: meta.next ?? null,
    mounts: meta.mounts ?? [],
    mountFiles: mountFiles(meta.mounts ?? [], repo, resultsIndex),
    assets: (meta.assets ?? []).map((a) => ({ name: a, url: `/data/lessons/${slug}/${a}` })),
    steps: raw.map((s) => ({ id: slugify(s.title), title: s.title, blocks: s.blocks })),
    exercise: {
      function: ex.function,
      hints: (ex.hints ?? []).map((h) => String(h).trim()),
      starter: readFileSync(join(cp, "starter.py"), "utf8").replace(/\n+$/, ""),
      solution: readFileSync(join(cp, "solution.py"), "utf8").replace(/\n+$/, ""),
      checker: readFileSync(join(cp, "checker.py"), "utf8"),
    },
    flashcards: (loadYaml(join(dir, "flashcards.yaml")) ?? []).map((c, i) => ({
      id: `${String(meta.id)}-${i + 1}`,
      q: String(c.q).trim(),
      a: String(c.a).trim(),
    })),
    errors: loadYaml(join(dir, "errors.yaml")) ?? [],
  };
  // stable ids for activities: <step id>.<kind><n>
  for (const s of lesson.steps) {
    const count = {};
    for (const b of s.blocks) {
      if (b.kind === "md") continue;
      count[b.kind] = (count[b.kind] ?? 0) + 1;
      b.id = `${s.id}.${b.kind}${count[b.kind]}`;
    }
  }
  return lesson;
}

export function validateLesson(L, allIds) {
  const p = [];
  if (!(L.minutes >= 45 && L.minutes <= 90)) p.push("a lesson must fit a 45-90 minute session");
  if (!L.slug.startsWith(`${L.id}-`)) p.push(`folder ${L.slug} does not start with id ${L.id}`);
  for (const pre of L.prerequisites) if (!allIds.has(pre)) p.push(`unknown prerequisite ${pre}`);
  if (L.next !== null && !allIds.has(L.next)) p.push(`unknown next lesson ${L.next}`);
  const ids = L.steps.map((s) => s.id);
  if (new Set(ids).size !== ids.length) p.push("duplicate step titles");
  let total = 0;
  let checkpoints = 0;
  for (const s of L.steps) {
    if (!s.blocks.some((b) => b.kind !== "md")) p.push(`step '${s.title}' has nothing to do`);
    for (const seg of proseSegments(s)) {
      const n = words(seg);
      total += n;
      if (n > PROSE_LIMIT) p.push(`step '${s.title}': ${n} words between interactive elements (limit ${PROSE_LIMIT})`);
    }
    for (const b of s.blocks) {
      if (b.kind === "checkpoint") checkpoints++;
      if (b.kind === "predict") {
        const q = b.data;
        if (!q.question || !q.explain) p.push(`step '${s.title}': predict needs question and explain`);
        if (q.options && !(Number.isInteger(q.answer) && q.answer >= 0 && q.answer < q.options.length))
          p.push(`step '${s.title}': predict answer must index options`);
      }
    }
  }
  const last = L.steps[L.steps.length - 1];
  if (checkpoints !== 1 || !last?.blocks.some((b) => b.kind === "checkpoint")) p.push("exactly one checkpoint, in the last step");
  if (total > LESSON_PROSE_LIMIT) p.push(`${total} words of prose (limit ${LESSON_PROSE_LIMIT})`);
  if (L.flashcards.length < 5 || L.flashcards.length > 10) p.push("need 5-10 flashcards");
  if (L.exercise.hints.length < 2 || L.exercise.hints.length > 4) p.push("checkpoint needs 2-4 hints");
  for (const e of L.errors) {
    if (!e.see || !e.match || !e.why || !e.fix) p.push("errors.yaml entry lacks see/match/why/fix");
    else
      try {
        new RegExp(e.match);
      } catch (err) {
        p.push(`bad regex ${e.match}: ${err}`);
      }
  }
  return p;
}

export function buildContent(repo) {
  const root = join(repo, "site", "content");
  const idxPath = join(repo, "site", "public", "data", "results", "index.json");
  const resultsIndex = existsSync(idxPath) ? JSON.parse(readFileSync(idxPath, "utf8")) : { runs: [] };
  const dirs = readdirSync(join(root, "lessons"), { withFileTypes: true })
    .filter((d) => d.isDirectory() && /^\d\d-/.test(d.name))
    .map((d) => d.name)
    .sort();
  const lessons = dirs.map((slug) => loadLesson(join(root, "lessons", slug), slug, repo, resultsIndex));
  const allIds = new Set(lessons.map((l) => l.id));
  const problems = lessons.flatMap((l) => validateLesson(l, allIds).map((x) => `${l.slug}: ${x}`));
  const errors = loadYaml(join(root, "errors.yaml")) ?? [];
  return { lessons, errors, problems };
}
