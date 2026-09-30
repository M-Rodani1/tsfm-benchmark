// Every lesson in a real browser (Pyodide from the CDN): all code cells run, the unsolved
// starter fails the checker with an explanation, and the solution passes. Also the flow
// "run an exercise that fails and then passes" with tiered hints.
// Needs cdn.jsdelivr.net; CI sets REQUIRE_PYODIDE=1 so these tests can never be skipped there.
import { expect, test, type Page } from "@playwright/test";
import { cdnReachable, content } from "./helpers";

// One page for all tests (like a learner moving between lessons in one tab). Not "serial":
// a failing lesson must not skip the others (Playwright then starts a fresh worker and page).
let page: Page;

test.beforeAll(async ({ browser }) => {
  const ok = await cdnReachable();
  if (!ok && process.env.REQUIRE_PYODIDE === "1") throw new Error("REQUIRE_PYODIDE=1 but cdn.jsdelivr.net is unreachable");
  test.skip(!ok, "Pyodide packages (cdn.jsdelivr.net) unreachable from this machine");
  page = await browser.newPage();
  page.on("dialog", (d) => void d.accept());
  page.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") console.log(`[browser ${m.type()}] ${m.text()}`); });
  page.on("pageerror", (e) => console.log(`[pageerror] ${e.message}`));
  page.on("crash", () => console.log("[crash] the page crashed"));
  page.on("requestfailed", (r) => console.log(`[requestfailed] ${r.url()} ${r.failure()?.errorText ?? ""}`));
  await page.goto("/lessons");
});

test.afterAll(async () => page?.close());

// On failure, print what the page shows (CI artifacts may be unreachable to whoever debugs).
// eslint-disable-next-line no-empty-pattern -- Playwright requires a destructuring pattern here
test.afterEach(async ({}, info) => {
  if (!page || info.status === info.expectedStatus) return;
  const responsive = await Promise.race([page.evaluate(() => true).catch(() => false), new Promise((r) => setTimeout(() => r(false), 5000))]);
  console.log(`[diagnostics] ${info.title}: main thread responsive: ${responsive}`);
  if (!responsive) return;
  const text = async (sel: string) => (await page.locator(sel).first().innerText({ timeout: 2000 }).catch(() => "(none)")).slice(0, 1500);
  console.log(`[diagnostics] python status: ${await text("[data-testid=py-status]")}`);
  console.log(`[diagnostics] checkpoint:\n${await text("[data-testid=checkpoint]")}`);
});

async function openCheckpoint(lessonId: string) {
  // in-app navigation (Python keeps running): a lesson page's top bar only leads back to Home
  const back = page.getByRole("link", { name: "Back to Home" });
  if (await back.count()) await back.click();
  await page.getByRole("link", { name: "Lessons", exact: true }).click();
  await page.getByTestId(`lesson-${lessonId}`).click();
  await page.locator("[data-testid=step], [data-testid=prereq-lock]").first().waitFor();
  if (await page.getByTestId("prereq-lock").count()) await page.getByTestId("override").click();
  const lesson = content.lessons.find((l) => l.id === lessonId)!;
  await page.getByRole("navigation", { name: "Steps of this lesson" }).getByRole("button", { name: lesson.steps[lesson.steps.length - 1].title }).click();
  await expect(page.getByTestId("checkpoint")).toBeVisible();
  return lesson;
}

async function check() {
  await page.getByTestId("check").click();
  const done = page.getByTestId("checkpoint").locator("[data-testid=pass], [data-testid=error-box]");
  await expect(done.first()).toBeVisible({ timeout: 200_000 });
}

test("an exercise that fails and then passes, with tiered hints", async () => {
  test.setTimeout(420_000);
  const lesson = await openCheckpoint("06");
  await check(); // unsolved starter
  const cp = page.getByTestId("checkpoint");
  await expect(cp.getByTestId("error-box")).toContainText("NotImplementedError");
  await expect(cp.getByTestId("error-explanation")).toContainText("placeholder");
  await cp.getByTestId("hint-button").click();
  await expect(cp.getByTestId("hints")).toContainText(/ratio/);
  const editor = cp.getByRole("textbox");
  await editor.fill("def my_qlike(y, f):\n    return f / y - np.log(f / y) - 1\n"); // a typical mistake
  await check();
  await expect(cp.getByTestId("error-box")).toContainText("Ratio upside down");
  await editor.fill(lesson.exercise.solution);
  await check();
  await expect(cp.getByTestId("pass")).toBeVisible();
  await page.reload(); // progress persisted
  await expect(page.getByTestId("checkpoint")).toContainText("passed before");
});

for (const lesson of content.lessons) {
  test(`lesson ${lesson.id}: every cell runs in the browser; starter fails, solution passes`, async () => {
    test.setTimeout(600_000);
    await openCheckpoint(lesson.id);
    const cp = page.getByTestId("checkpoint");
    const reset = cp.getByRole("button", { name: /Reset to starter/ });
    if (await reset.count()) await reset.click();
    await check(); // runs every earlier cell of the lesson first, then the starter
    const err = cp.getByTestId("error-box");
    await expect(err).toBeVisible();
    await expect(err).not.toContainText("An earlier cell"); // all lesson cells ran without error
    await expect(err).toContainText("NotImplementedError");
    await cp.getByRole("textbox").fill(lesson.exercise.solution);
    await check();
    await expect(cp.getByTestId("pass")).toBeVisible();
  });
}
