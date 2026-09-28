import { defineConfig, devices } from "@playwright/test";

/**
 * Browser tests run against the production build (`vite preview`, same security headers as
 * Netlify). Tests that execute Python need Pyodide's packages from the jsDelivr CDN; in CI
 * (REQUIRE_PYODIDE=1) they must run, locally they are skipped if the CDN is unreachable.
 * In the build container the preinstalled Chromium is used (PLAYWRIGHT_BROWSERS_PATH).
 */
export default defineConfig({
  testDir: "e2e",
  timeout: 240_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:4173",
    // a click that cannot happen fails with Playwright's reason instead of using up the test
    actionTimeout: 60_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run preview",
    url: "http://localhost:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
