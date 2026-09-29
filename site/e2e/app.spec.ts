// End-to-end flows that need no Python: steps, persistence, export/import, review, results.
import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { content, importProgress, localDate, progressFile, skipTour } from "./helpers";

test.beforeEach(async ({ page }) => {
  page.on("dialog", (d) => void d.accept());
});

test("home shows the next step, due cards and the pending terminal task", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/welcome$/); // first visit: the tour (tests/journey.spec.ts goes through it)
  await page.getByTestId("welcome-skip").click();
  await expect(page.getByTestId("next-action")).toContainText("Lesson 00");
  await expect(page.getByTestId("due-card")).toContainText("0");
  // the terminal work is on Home's path summary, the Research status page and its task pages
  await expect(page.getByTestId("path-summary")).toContainText("Launch the real study");
  await expect(page.getByTestId("path-summary")).toContainText("Publish the real results");
  await page.goto("/status");
  await expect(page.getByTestId("terminal-task")).toContainText("make reproduce");
  await expect(page.getByTestId("terminal-task")).toContainText("make publish-results");
  await page.goto("/tasks/run-study");
  await expect(page.getByTestId("task-page")).toContainText("make reproduce");
  await page.goto("/tasks/publish");
  await expect(page.getByTestId("task-page")).toContainText("make publish-results");
  await expect(page.getByTestId("local-only-banner")).toBeVisible();
});

test("complete a lesson step, then reload: progress and position persist", async ({ page }) => {
  await skipTour(page);
  await page.goto("/lessons/00");
  const step = page.getByTestId("step");
  await expect(step).toHaveAttribute("data-step", "what-runs-where");
  await step.getByTestId("predict").getByRole("button", { name: /own computer/ }).click();
  await expect(step.getByTestId("predict-feedback")).toContainText("Right");
  await expect(step).toContainText("step done");
  await page.getByTestId("next-step").click();
  await expect(page.getByTestId("step")).toHaveAttribute("data-step", "is-the-data-what-it-should-be");

  await page.reload();
  await expect(page.getByTestId("step")).toHaveAttribute("data-step", "is-the-data-what-it-should-be");
  await page.getByRole("button", { name: /What runs where/ }).click();
  await expect(page.getByTestId("predict-feedback")).toContainText("Right");
  await page.goto("/");
  await expect(page.getByTestId("next-action")).toContainText("Continue lesson 00");
  await expect(page.getByTestId("next-action")).toContainText("step 2 of 7");
  await expect(page.getByTestId("next-action-button")).toHaveAttribute("href", "/lessons/00?step=is-the-data-what-it-should-be");
});

test("code is autosaved as you type and survives closing the tab", async ({ page, context }) => {
  await page.goto("/lessons/01");
  await page.getByTestId("override").click(); // lesson 01 builds on 00: start anyway
  const editor = page.getByTestId("code-cell").first().getByRole("textbox");
  await editor.fill("print('my own edit')");
  await page.waitForTimeout(800); // debounce
  await page.close();
  const again = await context.newPage();
  await again.goto("/lessons/01");
  await expect(again.getByTestId("code-cell").first().getByRole("textbox")).toHaveValue("print('my own edit')");
  await expect(again.getByTestId("code-cell").first()).toContainText("edited (autosaved)");
});

test("export then import progress restores everything", async ({ page }) => {
  await page.goto("/lessons/00");
  await page.getByTestId("predict").getByRole("button", { name: /own computer/ }).click();
  await page.goto("/notes?lesson=00");
  await page.getByTestId("notes").fill("Pyodide = Python compiled to WebAssembly");
  await page.waitForTimeout(800);

  await page.goto("/account");
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByTestId("export").click()]);
  const file = await download.path();
  const exported = JSON.parse(readFileSync(file!, "utf8"));
  expect(exported.app).toBe("tsfm-reality-check");
  expect(exported.tables.notes[0].data.body).toContain("WebAssembly");

  await page.getByRole("button", { name: "Delete local progress" }).click();
  await expect(page.getByTestId("account-message")).toContainText("deleted");
  await page.goto("/notes?lesson=00");
  await expect(page.getByTestId("notes")).toHaveValue("");

  await page.goto("/account");
  await page.getByTestId("import-file").setInputFiles(file!);
  await expect(page.getByTestId("account-message")).toContainText("Imported");
  await page.goto("/notes?lesson=00");
  await expect(page.getByTestId("notes")).toHaveValue("Pyodide = Python compiled to WebAssembly");
  await page.goto("/lessons/00");
  await expect(page.getByTestId("predict-feedback")).toContainText("Right");
});

test("review due flashcards with the scheduler", async ({ page }) => {
  const lesson = content.lessons[0];
  const today = localDate();
  await importProgress(page, progressFile({
    flashcard_state: lesson.flashcards.slice(0, 3).map((c) => ({
      id: c.id, data: { card_id: c.id, lesson_id: lesson.id, ease: 2.5, interval_days: 0, repetitions: 0, lapses: 0, due: today, last_reviewed: null },
    })),
  }));
  await page.goto("/");
  await expect(page.getByTestId("due-card")).toContainText("3");
  await page.getByRole("link", { name: /Review now/ }).click();
  for (let i = 0; i < 3; i++) {
    await expect(page.getByTestId("card-front")).toBeVisible();
    await page.getByTestId("show-answer").click();
    await expect(page.getByTestId("card-back")).toBeVisible();
    await page.getByTestId(i === 0 ? "grade-again" : "grade-good").click();
  }
  await expect(page.getByTestId("nothing-due")).toContainText("3 cards reviewed");
  await page.reload();
  await expect(page.getByTestId("nothing-due")).toContainText("Next cards are due on");
  await page.goto("/notes");
  await expect(page.getByTestId("session-log")).toContainText("cards reviewed");
});

test("results page shows stored results with provenance and the synthetic label", async ({ page }) => {
  await page.goto("/results");
  await expect(page.getByTestId("synthetic-banner")).toContainText("SYNTHETIC — not research results");
  await expect(page.getByTestId("primary-card")).toContainText("UNAVAILABLE");
  await expect(page.getByTestId("dm-matrix")).toBeVisible();
  await expect(page.getByTestId("lossdiff-chart")).toBeVisible();
  await expect(page.getByTestId("provenance").first()).toContainText(/config [0-9a-f]{16}/);
  await expect(page.getByTestId("limitations")).toContainText("Synthetic data");
  await page.getByTestId("f-target").selectOption("returns");
  await expect(page.getByTestId("primary-card")).toContainText("returns, h = 1");
  await page.getByTestId("f-run").selectOption("smoke");
  await expect(page.getByTestId("provenance").first()).toContainText("run smoke");
});

test("prerequisite locks can be overridden", async ({ page }) => {
  await page.goto("/lessons/04");
  await expect(page.getByTestId("prereq-lock")).toContainText("01, 02, 03");
  await page.getByTestId("override").click();
  await expect(page.getByTestId("step")).toBeVisible();
});

test("the site works offline after a first visit", async ({ page, context }) => {
  await page.goto("/");
  await page.evaluate(async () => { await navigator.serviceWorker.ready; });
  await page.reload(); // now controlled by the service worker, which caches the shell
  await page.goto("/lessons");
  await page.goto("/results");
  await expect(page.getByTestId("primary-card")).toBeVisible();
  await context.setOffline(true);
  await page.goto("/lessons");
  await expect(page.getByTestId("lesson-00")).toBeVisible();
  await page.goto("/results");
  await expect(page.getByTestId("primary-card")).toBeVisible();
  await context.setOffline(false);
});

test("a browser that used the site before an update (older local database) still starts and keeps its progress", async ({ page }) => {
  // Before the guided journey the site created IndexedDB "tsfm-rc" at version 1 with seven
  // tables. Recreate exactly that, with some progress in it, before the app first loads.
  await page.goto("/favicon.svg"); // same origin, no app code
  await page.evaluate(async () => {
    const OLD = ["lesson_progress", "exercise_attempts", "exercise_drafts", "notes", "flashcard_state", "review_log", "session_log"];
    await new Promise<void>((resolve, reject) => {
      const req = indexedDB.open("tsfm-rc", 1);
      req.onupgradeneeded = () => {
        for (const t of OLD) req.result.createObjectStore(t, { keyPath: "id" });
        req.result.createObjectStore("meta");
      };
      req.onerror = () => reject(req.error);
      req.onsuccess = () => {
        const db = req.result;
        const tx = db.transaction("notes", "readwrite");
        tx.objectStore("notes").put({ id: "00", data: { lesson_id: "00", body: "written before the update" }, updated_at: new Date().toISOString(),
          deleted: false, dirty: true });
        tx.oncomplete = () => { db.close(); resolve(); };
      };
    });
  });
  await page.goto("/"); // was a blank page: NotFoundError "object store was not found"
  await expect(page.getByTestId("welcome")).toBeVisible();
  await page.goto("/notes?lesson=00");
  await expect(page.getByTestId("notes")).toHaveValue("written before the update");
});

test("while an old tab still holds the old database open, a new tab says so, then starts once it is closed", async ({ context }) => {
  const oldTab = await context.newPage();
  await oldTab.goto("/favicon.svg");
  await oldTab.evaluate(async () => {
    const OLD = ["lesson_progress", "exercise_attempts", "exercise_drafts", "notes", "flashcard_state", "review_log", "session_log"];
    await new Promise<void>((resolve, reject) => {
      const req = indexedDB.open("tsfm-rc", 1);
      req.onupgradeneeded = () => {
        for (const t of OLD) req.result.createObjectStore(t, { keyPath: "id" });
        req.result.createObjectStore("meta");
      };
      req.onerror = () => reject(req.error);
      // keep the connection open, like a tab running the old site (it never closes it)
      req.onsuccess = () => { (window as unknown as { oldDb: IDBDatabase }).oldDb = req.result; resolve(); };
    });
  });
  const page = await context.newPage();
  await page.goto("/");
  await expect(page.getByTestId("boot-message")).toContainText("Close the other tabs of this site");
  await oldTab.close();
  await expect(page.getByTestId("welcome")).toBeVisible();
});
