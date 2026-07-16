import { expect, test } from "@playwright/test";

// ponytail: trivial test just proves the placeholder renders + Playwright is wired.
test("placeholder renders", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Berth Allocation Quantum" }),
  ).toBeVisible();
});
