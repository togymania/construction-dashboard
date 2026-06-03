import { expect, test } from "@playwright/test";

/**
 * Critical-flow smoke tests (Faz 2.5 — S5).
 *
 * These cover the flows the audit cared about: that a user can log in,
 * the dashboard renders its KPIs, and — crucially — that the "spent %"
 * the Single-Source-of-Truth work unified shows the SAME value on the
 * dashboard and the budget page (the audit found 0% / 72% / 61.4% / 2%).
 *
 * NOTE: locators use accessible text/roles. If your markup differs,
 * adjust the selectors — these are a starting scaffold, not yet run in
 * this environment.
 */
const EMAIL = process.env.E2E_EMAIL ?? "admin@example.com";
const PASSWORD = process.env.E2E_PASSWORD ?? "admin123";

async function login(page) {
  await page.goto("/login");
  // Email + password fields, then submit.
  await page.getByLabel(/e-?mail/i).fill(EMAIL).catch(async () => {
    await page.locator('input[type="email"]').fill(EMAIL);
  });
  await page.getByLabel(/password|parola|şifre/i).fill(PASSWORD).catch(async () => {
    await page.locator('input[type="password"]').fill(PASSWORD);
  });
  await page.getByRole("button", { name: /log ?in|giriş|sign ?in/i }).click();
  await expect(page).toHaveURL(/\/(dashboard)?$|\/$/, { timeout: 15_000 });
}

test.describe("smoke", () => {
  test("login lands on the dashboard", async ({ page }) => {
    await login(page);
    // The four KPI cards should be present.
    await expect(page.getByText(/active projects/i)).toBeVisible();
    await expect(page.getByText(/total budget/i)).toBeVisible();
  });

  test("can open a project and its budget page", async ({ page }) => {
    await login(page);
    await page.goto("/projects");
    await expect(page.getByText(/projects?/i).first()).toBeVisible();
    // Open the first project row.
    await page.getByRole("row").nth(1).click().catch(() => {});
    await expect(page).toHaveURL(/\/projects\/\d+/);
  });

  /**
   * SSOT consistency: the spent/utilisation percentage must agree between
   * surfaces. This is the regression guard for the F1.5 fix. Fill in the
   * exact selectors/test-ids for your KPI elements to enable the strict
   * assertion.
   */
  test.fixme("spent % is consistent across dashboard and budget", async ({ page }) => {
    await login(page);
    // 1) read the dashboard "used %" ; 2) open budget; 3) read its "used %"
    // 4) assert they match (allowing for budget-vs-planned labelling).
  });
});
