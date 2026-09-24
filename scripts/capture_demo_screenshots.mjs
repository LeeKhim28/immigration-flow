import { chromium } from "../apps/immigration-flow-web/node_modules/@playwright/test/index.mjs";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const output = resolve("docs/assets/demo");
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });

await page.goto("http://127.0.0.1:4173");
await page.screenshot({ path: resolve(output, "landing-desktop.png"), fullPage: true });
await page.getByRole("link", { name: /explore as applicant/i }).click();
await page.getByRole("link", { name: /requirements/i }).click();
await page.getByRole("heading", { name: /requirements and document readiness/i }).waitFor();
await page.screenshot({ path: resolve(output, "applicant-requirements-desktop.png"), fullPage: true });
await page.getByRole("link", { name: /readiness/i }).click();
await page.screenshot({ path: resolve(output, "applicant-readiness-desktop.png"), fullPage: true });

await page.setViewportSize({ width: 390, height: 844 });
await page.goto(page.url().replace(/\/evaluation$/, ""));
await page.getByRole("heading", { name: /IF-DEMO-STUDENT-PASS/i }).waitFor();
await page.screenshot({ path: resolve(output, "applicant-overview-mobile.png"), fullPage: true });
await page.setViewportSize({ width: 1440, height: 1000 });

await page.getByRole("link", { name: /handover/i }).click();
await page.getByRole("button", { name: /submit to immigration/i }).click();
await page.getByRole("button", { name: /confirm handover/i }).click();
await page.getByText(/handover recorded at/i).waitFor();
await page.getByRole("link", { name: /switch workspace/i }).click();
await page.getByRole("link", { name: /explore as officer/i }).click();
let submittedCases = page.getByRole("link", { name: /IF-DEMO-STUDENT-PASS/i });
await submittedCases.first().waitFor();
while ((await submittedCases.count()) > 1) {
  await submittedCases.first().click();
  await page.getByRole("button", { name: /start processing/i }).click();
  await page.getByText("Processing started.", { exact: true }).waitFor();
  await page.goto("http://127.0.0.1:4173/officer/cases");
  submittedCases = page.getByRole("link", { name: /IF-DEMO-STUDENT-PASS/i });
  await submittedCases.first().waitFor();
}
await page.screenshot({ path: resolve(output, "officer-queue-desktop.png"), fullPage: true });
await submittedCases.first().click();
await page.getByRole("heading", { name: /audit timeline/i }).waitFor();
await page.screenshot({ path: resolve(output, "officer-case-timeline-desktop.png"), fullPage: true });

await browser.close();
