// Every lesson in a real browser (Pyodide from the CDN): all code cells run, the unsolved
// starter fails the checker with an explanation, and the solution passes. Also the flow
// "run an exercise that fails and then passes" with tiered hints.
// Needs cdn.jsdelivr.net; CI sets REQUIRE_PYODIDE=1 so these tests can never be skipped there.
import { expect, test, type Page } from "@playwright/test";
import { cdnReachable, content } from "./helpers";

test.describe.configure({ mode: "serial" });
let page: Page;

test.beforeAll(async ({ browser }) => {
  const ok = await cdnReachable();
  if (!ok && process.env.REQUIRE_PYODIDE === "1") throw new Error("REQUIRE_PYODIDE=1 but cdn.jsdelivr.net is unreachable");
  test.skip(!ok, "Pyodide packages (cdn.jsdelivr.net) unreachable from this machine");
  page = await browser.newPage();
  page.on("dialog", (d) => void d.accept());
  page.on("console", (m) => { if (m.type() === "error") console.log(`[browser] ${m.text()}`); });
  await page.goto("/lessons");
});

test.afterAll(async () => page?.close());

async function openCheckpoint(lessonId: string) {
  await page.getByRole("link", { name: "Lessons", exact: true }).click();
  await page.getByTestId(`lesson-${lessonId}`).click();
  if (await page.getByTestId("override").isVisible()) await page.getByTestId("override").click();
  const lesson = content.lessons.find((l) => l.id === lessonId)!;
  await page.getByRole("button", { name: lesson.steps[lesson.steps.length - 1].title }).click();
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
    await cp.getByRole("button", { name: /Reset to starter/ }).click().catch(() => {});
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
