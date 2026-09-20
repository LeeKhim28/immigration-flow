import { expect, test } from "@playwright/test";

test("synthetic case moves from applicant handover to officer processing", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: /explore as applicant/i }).click();
  await page.getByRole("link", { name: /requirements/i }).click();
  await expect(page.getByRole("heading", { name: /official requirements/i })).toBeVisible();

  await page.getByRole("link", { name: /handover/i }).click();
  await page.getByRole("button", { name: /submit to immigration/i }).click();
  await page.getByRole("button", { name: /confirm handover/i }).click();
  await expect(page.getByText(/handover recorded at/i)).toBeVisible();

  await page.getByRole("link", { name: /switch workspace/i }).click();
  await page.getByRole("link", { name: /explore as officer/i }).click();
  await page.getByRole("link", { name: /IF-DEMO-STUDENT-PASS/i }).click();
  await page.getByRole("button", { name: /start processing/i }).click();
  await expect(page.getByText(/processing started/i)).toBeVisible();
});
