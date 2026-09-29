// The study-console design in a real browser: the chart question's states, the study table and
// its paste check on Home, the responsive rules (390 px: no sideways scroll, 44 px targets, the
// next action above the fold; below 860 px the rail is a disclosure) and an axe scan of the main
// pages in light and dark. Rules: site/DESIGN.md.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { content, importProgress, progressFile, tourSeen } from "./helpers";

const capture = (name: string) => readFileSync(fileURLToPath(new URL(`../tests/fixtures/cli/${name}`, import.meta.url)), "utf8");
const done = (id: string) => ({ id, data: { lesson_id: id, status: "completed", current_step: "x", completed_steps: [], activities: {}, prereq_override: false,
  started_at: null, completed_at: new Date().toISOString() } });
const PREDICT = "/lessons/02?step=volatility-comes-in-clusters";
const running = () => progressFile({
  lesson_progress: [done("00"), done("01")],
  journey_state: [tourSeen,
    { id: "task:setup", data: { step_key: "task:setup", status: "done", method: "self-reported", detail: "self-reported", started_at: null, done_at: null } },
    { id: "task:run-study", data: { step_key: "task:run-study", status: "started", method: null, detail: "", started_at: new Date().toISOString(), done_at: null } }],
});

test.beforeEach(async ({ page }) => {
  page.on("dialog", (d) => void d.accept());
});

test("chart question: check waits for an answer, the forecast is drawn dashed, what happened draws on check", async ({ page }) => {
  await importProgress(page, progressFile({ lesson_progress: [done("00"), done("01")] }));
  await page.goto(PREDICT);
  const q = page.getByTestId("predict");
  const chart = q.getByTestId("forecast-chart");
  await expect(chart).toHaveAttribute("data-revealed", "false");
  await expect(chart).toContainText("Not yet seen");
  // nothing chosen: the check is disabled and says why
  await expect(q.getByTestId("predict-check")).toBeDisabled();
  await expect(q.getByTestId("predict-check")).toHaveText("Check what happened");
  await expect(q).toContainText("Choose an answer first.");
  await expect(q.getByRole("group")).toContainText("Over the next 40 days"); // fieldset + legend
  // choosing draws the forecast and tags the option
  await q.getByRole("radio", { name: /Snap back/ }).check();
  await expect(q.getByTestId("forecast-line")).toHaveCount(1);
  await expect(q.locator(".option.selected")).toContainText("Your forecast");
  await q.getByRole("radio", { name: /fade slowly/ }).check();
  await expect(q.locator(".option.selected")).toContainText("fade slowly");
  await q.getByTestId("predict-check").click();
  // revealed: the realised path, the verdict, the tally over all similar shocks, both tags on one option
  await expect(chart).toHaveAttribute("data-revealed", "true");
  await expect(chart.locator("path.realised")).toHaveCount(1);
  const fb = q.getByTestId("predict-feedback");
  await expect(fb).toContainText("Right");
  await expect(fb).toContainText("similar shocks in the 3 GARCH series");
  await expect(q.locator(".option.selected")).toContainText("Your forecast, and what happened");
  await expect(q.locator("[aria-live=polite] [data-testid=predict-feedback]")).toHaveCount(1);
  await expect(page.getByTestId("step")).toContainText("Step done");
  // try again: explore another answer; the stored first answer does not change
  await q.getByTestId("predict-retry").click();
  await expect(chart).toHaveAttribute("data-revealed", "false");
  await q.getByRole("radio", { name: /Keep climbing/ }).check();
  await q.getByTestId("predict-check").click();
  await expect(fb).toContainText("Not quite");
  await expect(q.locator(".option").filter({ hasText: "fade slowly" })).toContainText("What happened");
  await expect(fb).toContainText("Your first answer is the one kept");
  await page.reload();
  await expect(page.getByTestId("predict-feedback")).toContainText("Right");
  // continue moves on to the next thing to do in the step
  await page.getByTestId("predict-continue").click();
  await expect(page.getByTestId("next-step")).toBeFocused();
});

test("Home: the study table says how the site knows, and 'It has finished' opens the paste check", async ({ page }) => {
  await importProgress(page, running());
  await page.goto("/");
  await expect(page.getByTestId("next-action-context")).toHaveText("Phase 3 · Foundations · lesson 2 of 4");
  await expect(page.getByTestId("next-action-title")).toHaveText(`Next: ${content.lessons[2].title}`);
  for (const stage of ["data", "baselines", "foundation-models", "statistics"])
    await expect(page.getByTestId(`study-${stage}`)).toHaveAttribute("data-status", "Running");
  await expect(page.getByTestId("study-table")).toContainText("Self-reported: you started it");
  await expect(page.getByTestId("study-publish")).toHaveAttribute("data-status", "Waiting");
  // models under test come from study.json (config + buffer), formatted as dates
  const models = page.getByTestId("models-under-test");
  await expect(models).toContainText("Chronos-Bolt tiny");
  await expect(models).toContainText("26 Dec 2024");
  // the rail: current phase highlighted, the running study marked as such
  await expect(page.getByTestId("rail-P2")).toContainText("Running on your laptop");
  await expect(page.getByTestId("rail-P3")).toHaveAttribute("aria-current", "step");
  // the paste check in a dialog; a finished run of the fixtures is not the real study
  await page.getByTestId("study-finished").click();
  const dialog = page.getByTestId("finished-dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByTestId("task-output").fill(capture("reproduce_fixtures_ok.txt"));
  await dialog.getByTestId("task-check-button").click();
  await expect(dialog.getByTestId("task-result")).toHaveAttribute("data-verdict", "failure");
  await expect(dialog.getByTestId("task-result")).toContainText("not of the real study");
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(page.getByTestId("study-data")).toHaveAttribute("data-status", "Running");
});

async function noSidewaysScroll(page: Page, path: string) {
  const over = await page.evaluate(() => {
    const w = document.documentElement.clientWidth;
    // wide tables may scroll inside their own box (.tablewrap); nothing may widen the page
    const inScroller = (e: HTMLElement) => !!e.parentElement?.closest(".tablewrap, pre, .output, textarea, .editor");
    const wide = [...document.querySelectorAll<HTMLElement>("body *")].filter((e) => e.getBoundingClientRect().right > w + 1 && !inScroller(e))
      .map((e) => `${e.tagName.toLowerCase()}.${e.className}`).slice(0, 3);
    return { extra: document.documentElement.scrollWidth - w, wide };
  });
  expect(over, path).toEqual({ extra: 0, wide: [] });
}

test.describe("at 390 px", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true });

  test("no sideways scroll, 44 px targets, the next action above the fold, the rail as a disclosure", async ({ page }) => {
    await importProgress(page, running());
    for (const path of ["/", "/path", "/results", "/lessons", "/review", "/notes", "/tasks/setup", PREDICT]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await noSidewaysScroll(page, path);
    }
    await page.goto("/");
    const button = page.getByTestId("next-action-button");
    const box = (await button.boundingBox())!;
    expect(box.y + box.height).toBeLessThanOrEqual(844);
    for (const el of [button, page.getByTestId("rail-toggle"), page.getByTestId("account-button"), page.getByRole("button", { name: "Menu" })])
      expect((await el.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    // the rail is one button until opened
    const toggle = page.getByTestId("rail-toggle");
    await expect(toggle).toHaveText(/Your path: Phase 3 of 8, Foundations/);
    await expect(page.getByTestId("rail-P0")).toBeHidden();
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByTestId("rail-P0")).toBeVisible();
    // the menu opens the sections
    await page.getByRole("button", { name: "Menu" }).click();
    await page.getByRole("link", { name: "Lessons", exact: true }).click();
    await expect(page).toHaveURL(/\/lessons$/);
    // tables stack into label/value rows
    await page.goto("/");
    await expect(page.getByTestId("study-data").locator("td").first()).toHaveCSS("display", "grid");
  });
});

for (const scheme of ["light", "dark"] as const) {
  test(`axe finds no WCAG A/AA violations (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await importProgress(page, running());
    const pages: [string, (() => Promise<void>) | null][] = [
      ["/", null], ["/path", null], ["/lessons", null], ["/tasks/run-study", null], ["/review", null], ["/notes", null], ["/account", null],
      ["/results", async () => { await page.getByTestId("primary-card").waitFor(); }],
      [PREDICT, async () => {
        await page.getByRole("radio", { name: /fade slowly/ }).check();
        await page.getByTestId("predict-check").click();
      }],
    ];
    for (const [path, then] of pages) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      if (then) await then();
      const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
      expect(r.violations.map((v) => `${path}: ${v.id} (${v.nodes.length}) ${v.nodes[0]?.target.join(" ")} — ${v.help}`)).toEqual([]);
    }
  });
}
