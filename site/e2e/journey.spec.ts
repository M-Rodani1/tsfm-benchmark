// The guided journey in a real browser (no Python needed): the first-visit tour, the next
// action after lesson 00, a pasted doctor output completing Phase 1, and all of it surviving a
// reload. The pasted outputs are real captures (tests/fixtures/cli, see its README).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";
import { content, importProgress, progressFile } from "./helpers";

const capture = (name: string) => readFileSync(fileURLToPath(new URL(`../tests/fixtures/cli/${name}`, import.meta.url)), "utf8");
const journey = JSON.parse(readFileSync(fileURLToPath(new URL("../src/generated/content.json", import.meta.url)), "utf8")).journey as {
  welcome: { title: string }[]; phases: { id: string; title: string }[];
};

test.beforeEach(async ({ page }) => {
  page.on("dialog", (d) => void d.accept());
});

/** Lesson 00 with every activity done except the first prediction (which the test answers). */
function lesson00AlmostDone() {
  const L = content.lessons[0];
  const at = new Date().toISOString();
  const activities: Record<string, object> = {};
  let skipped = false;
  for (const step of L.steps)
    for (const b of step.blocks as { kind: string; id?: string }[]) {
      if (b.kind === "md" || !b.id) continue;
      if (b.kind === "predict" && !skipped) {
        skipped = true;
        continue;
      }
      activities[b.id] = b.kind === "python" ? { kind: "python", ok: true, at }
        : b.kind === "checkpoint" ? { kind: "checkpoint", passed: true, at, hints_used: 0, solution_viewed: false }
        : { kind: "predict", answer: 0, correct: null, at };
    }
  return progressFile({
    lesson_progress: [{ id: "00", data: { lesson_id: "00", status: "in_progress", current_step: L.steps[0].id, completed_steps: [], activities,
      prereq_override: false, started_at: at, completed_at: null } }],
  });
}

async function expectNext(page: Page, text: RegExp | string, href: string) {
  await page.goto("/");
  await expect(page.getByTestId("next-action-title")).toContainText(text);
  await expect(page.getByTestId("next-action-button")).toHaveAttribute("href", href);
}

test("first visit goes through the welcome tour to lesson 00", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/welcome$/);
  for (const [i, screen] of journey.welcome.entries()) {
    await expect(page.getByTestId("welcome")).toHaveAttribute("data-screen", String(i + 1));
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(screen.title);
    if (i < journey.welcome.length - 1) await page.getByTestId("welcome-next").click();
  }
  // the last screen shows the route at a glance
  for (const p of journey.phases) await expect(page.getByTestId("welcome-route")).toContainText(p.title);
  await page.getByTestId("welcome-start").click();
  await expect(page).toHaveURL(/\/lessons\/00$/);
  await expect(page.getByTestId("lesson-intro")).toBeVisible();
  await expect(page.getByTestId("breadcrumb")).toHaveText("Phase 0 · Start here · step 2 of 2");
  // the tour does not come back by itself, but the menu re-opens it
  await expectNext(page, "Lesson 00", "/lessons/00?step=what-runs-where");
  await page.getByRole("link", { name: "Tour", exact: true }).click();
  await expect(page.getByTestId("welcome")).toHaveAttribute("data-screen", "1");
});

test("finishing lesson 00 leads to Phase 1; a pasted doctor success completes it; a reload keeps everything", async ({ page }) => {
  await importProgress(page, lesson00AlmostDone());
  await expectNext(page, "Continue lesson 00", "/lessons/00?step=what-runs-where");

  // finish lesson 00 by answering its last open activity
  await page.getByTestId("next-action-button").click();
  await page.getByTestId("predict").getByRole("button", { name: /own computer/ }).click();
  await expect(page.getByTestId("step")).toContainText("step done");
  const L = content.lessons[0];
  await page.getByRole("button", { name: L.steps[L.steps.length - 1].title }).click();
  await expect(page.getByTestId("lesson-complete")).toBeVisible();
  // the end of the lesson: ONE next step, from the journey (not "next lesson")
  await expect(page.getByTestId("journey-next-button")).toHaveCount(1);
  await expect(page.getByTestId("journey-next-button")).toContainText("Set up your laptop");
  await expectNext(page, "Set up your laptop", "/tasks/setup");
  await expect(page.getByTestId("next-action-alternative")).toHaveAttribute("href", "/lessons/01");

  // the P1 task page: breadcrumb, numbered commands with copy buttons, the check
  await page.getByTestId("next-action-button").click();
  await expect(page.getByTestId("breadcrumb")).toHaveText("Phase 1 · Set up your laptop · step 1 of 1");
  await expect(page.getByTestId("task-status")).toHaveAttribute("data-status", "next");
  expect(await page.getByTestId("task-command").count()).toBeGreaterThanOrEqual(7);
  await expect(page.getByTestId("task-page")).toContainText("make doctor ONLINE=1");

  // a failed doctor run is explained and does not count
  await page.getByTestId("task-output").fill(capture("doctor_online_blocked.txt"));
  await page.getByTestId("task-check-button").click();
  await expect(page.getByTestId("task-result")).toHaveAttribute("data-verdict", "failure");
  await expect(page.getByTestId("task-result")).toContainText("Check your internet connection/proxy");
  await expect(page.getByTestId("task-status")).not.toHaveAttribute("data-status", "done");

  // the success output marks Phase 1 done
  await page.getByTestId("task-output").fill(capture("doctor_ok_staged_weights.txt"));
  await page.getByTestId("task-check-button").click();
  await expect(page.getByTestId("task-result")).toHaveAttribute("data-verdict", "success");
  await expect(page.getByTestId("task-status")).toHaveAttribute("data-status", "done");
  await expect(page.getByTestId("task-done")).toContainText("checked from your pasted output");
  await expect(page.getByTestId("journey-next-button")).toContainText("Launch the real study");

  // Home now says: launch the study, and keep learning while it runs
  await expectNext(page, "Launch the real study", "/tasks/run-study");
  await expect(page.getByTestId("next-action-note")).toHaveText("Start this now and keep learning while it runs.");

  // a reload keeps all of it (and never shows the tour again)
  await page.reload();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("next-action-title")).toContainText("Launch the real study");
  await page.goto("/path");
  await expect(page.getByTestId("phase-P0")).toHaveAttribute("data-status", "done");
  await expect(page.getByTestId("phase-P1")).toHaveAttribute("data-status", "done");
  await expect(page.getByTestId("step-task:setup")).toHaveAttribute("data-status", "done");
  await expect(page.getByTestId("step-task:setup")).toContainText("checked from pasted output");
  await expect(page.getByTestId("step-task:run-study")).toHaveAttribute("data-status", "next");
  await expect(page.getByTestId("path-progress")).toContainText("3 of 17 steps done");
  await page.reload();
  await expect(page.getByTestId("phase-P1")).toHaveAttribute("data-status", "done");
  await page.goto("/lessons");
  await expect(page.getByTestId("lesson-00")).toContainText("done");
});

test("while the study runs, lessons come next and Home says so; self-reported steps are labelled", async ({ page }) => {
  await importProgress(page, progressFile({
    lesson_progress: [{ id: "00", data: { lesson_id: "00", status: "completed", current_step: "x", completed_steps: [], activities: {}, prereq_override: false,
      started_at: null, completed_at: new Date().toISOString() } }],
    journey_state: [{ id: "site:welcome", data: { step_key: "site:welcome", status: "done", method: "site", detail: "", started_at: null, done_at: null } }],
  }));
  await page.goto("/tasks/setup");
  await page.getByTestId("task-self-report").click();
  await expect(page.getByTestId("task-done")).toContainText("self-reported");
  await page.goto("/tasks/run-study");
  await expect(page.getByTestId("task-note")).toHaveText("Start this now and keep learning while it runs.");
  await page.getByTestId("os-macos").click();
  await expect(page.getByTestId("task-page")).toContainText("caffeinate -i make reproduce");
  await page.getByTestId("os-linux").click();
  await expect(page.getByTestId("task-page")).toContainText("systemd-inhibit --what=idle:sleep make reproduce");
  await page.getByTestId("task-start").click();
  await expect(page.getByTestId("task-started")).toBeVisible();
  await page.goto("/");
  await expect(page.getByTestId("study-running")).toContainText("Keep going with lessons. Come back here when it finishes");
  await expect(page.getByTestId("next-action-title")).toContainText("Lesson 01");
  await page.goto("/path");
  await expect(page.getByTestId("step-task:setup")).toContainText("self-reported");
  await expect(page.getByTestId("step-task:run-study")).toHaveAttribute("data-status", "in_progress");
  // undo: the step is open again
  await page.goto("/tasks/setup");
  await page.getByTestId("task-reset").click();
  await expect(page.getByTestId("task-done")).toHaveCount(0);
});

test("lesson 09 and the Results page explain the SYNTHETIC results and how to unlock the real ones, without locking", async ({ page }) => {
  await page.goto("/lessons/09");
  const banner = page.getByTestId("synthetic-banner");
  await expect(banner).toContainText("SYNTHETIC");
  await expect(banner.getByRole("link", { name: /Phase 2/ })).toHaveAttribute("href", "/tasks/run-study");
  await expect(banner.getByRole("link", { name: /Phase 5/ })).toHaveAttribute("href", "/tasks/publish");
  await expect(page.getByTestId("breadcrumb")).toHaveText("Phase 6 · Read your results · step 1 of 2");
  if (await page.getByTestId("prereq-lock").count()) await page.getByTestId("override").click(); // prerequisites: a soft lock
  await expect(page.getByTestId("step")).toBeVisible(); // usable on synthetic data
  await page.goto("/results");
  await expect(page.getByTestId("synthetic-banner").getByRole("link", { name: /Phase 5/ })).toHaveAttribute("href", "/tasks/publish");
});
