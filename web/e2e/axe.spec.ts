import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const THEMES = ["light", "dark"] as const;

async function setTheme(page: Page, theme: "light" | "dark") {
  await page.addInitScript((t) => {
    window.localStorage.setItem("braille-press:theme", t);
  }, theme);
}

async function runAxe(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
}

for (const theme of THEMES) {
  test.describe(`axe — ${theme} theme`, () => {
    test.beforeEach(async ({ page }) => {
      await setTheme(page, theme);
    });

    test("Library page has no serious/critical violations", async ({ page }) => {
      await page.goto("/");
      const violations = await runAxe(page);
      expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
    });

    test("Circuit page, reader mode, has no serious/critical violations", async ({ page }) => {
      await page.goto("/circuit/015");
      const violations = await runAxe(page);
      expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
    });

    test("Circuit page, review mode, has no serious/critical violations", async ({ page }) => {
      await page.goto("/circuit/097");
      await page.getByText("Review (teacher)").click();
      const violations = await runAxe(page);
      expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
    });

    test("Status page has no serious/critical violations", async ({ page }) => {
      await page.goto("/status");
      const violations = await runAxe(page);
      expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
    });
  });
}
