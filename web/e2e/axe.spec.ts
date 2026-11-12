import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const THEMES = ["light", "dark"] as const;

async function expectAccessible(page: Page) {
  const { violations } = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
}

for (const theme of THEMES) {
  test.describe(`axe — ${theme} theme`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((t) => {
        window.localStorage.setItem("braille-press:theme", t);
      }, theme);
    });

    for (const [url, title] of [
      ["/", "Read a circuit diagram"],
      ["/try", "1. Add an image"],
      ["/library", "Library"],
      ["/status", "Status"],
      ["/circuit/015", "Circuit 015"],
    ]) {
      test(`${url} has no WCAG violations`, async ({ page }) => {
        await page.goto(url);
        await expect(page.getByRole("heading", { name: title, exact: false }).first()).toBeVisible();
        await expectAccessible(page);
      });
    }

    test("Circuit review has no WCAG violations", async ({ page }) => {
      await page.goto("/circuit/097");
      await page.getByText("Review (teacher)").click();
      await expect(page.getByRole("heading", { name: /Flagged parts/ })).toBeVisible();
      await expectAccessible(page);
    });

    test("Live reading and result steps have no WCAG violations", async ({ page }) => {
      test.setTimeout(60_000);
      await page.goto("/try");
      const engine = page.getByRole("status").filter({ hasText: /^Engine (ready|offline)$/ });
      await expect(engine).toBeVisible({ timeout: 10_000 });
      test.skip(await engine.textContent() === "Engine offline",
        "The local analysis engine is offline; live reading and result require real inference.");

      await page.getByRole("switch", { name: /Use the saved result/ }).click();

      // Hold the first real job response while axe checks the reading view.
      // This works even when the CPU finishes before Chromium starts the scan.
      let release!: () => void;
      const scanned = new Promise<void>((resolve) => { release = resolve; });
      await page.route("**/api/jobs/*", async (route) => {
        const response = await route.fetch();
        await scanned;
        await route.fulfill({ response });
      }, { times: 1 });

      await page.getByRole("button", { name: "Example 015" }).click();
      await expect(page).toHaveURL(/run=[a-f0-9]{64}&job=/);
      try {
        await expect(page.getByRole("heading", { name: "2. Reading the circuit" })).toBeVisible();
        await expectAccessible(page);
      } finally {
        release();
      }

      const heading = page.getByRole("heading", { name: "3. Result" });
      await expect(heading).toBeFocused({ timeout: 40_000 });
      await expect(page.getByText("Machine-read, not yet checked by a teacher")).toBeVisible();
      await expectAccessible(page);
      await page.getByText("Review (teacher)").click();
      await expectAccessible(page);
      await page.reload();
      await expect(page.getByText(/Saved result from/)).toBeVisible();
      await expect(page.getByRole("link", { name: "All layers" })).toBeVisible();
    });
  });
}
