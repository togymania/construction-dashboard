import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E config (Faz 2.5 — S5).
 *
 * Until now every test was a backend unit test; nothing exercised the
 * real user flows. These run against a locally served frontend.
 *
 * Setup (one time):
 *   cd frontend
 *   npm i -D @playwright/test
 *   npx playwright install
 *
 * Run:
 *   npm run test:e2e          # starts `next dev` and runs the specs
 *
 * Point at a deployed environment instead with:
 *   E2E_BASE_URL=https://monart-stroy-pm.vercel.app npx playwright test
 */
const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  // Only auto-start a dev server when testing locally.
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: "npm run dev",
        url: "http://localhost:3000",
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
});
