import { expect, test } from "@playwright/test";
import { installAlphaSession, mockProductApi, testLeagueUuid } from "./api-mocks";

test("data health explains withheld scores and unavailable FAAB context", async ({ page }) => {
  await mockProductApi(page);
  await installAlphaSession(page);

  await page.goto(`/leagues/${testLeagueUuid}/data-health`);

  await expect(page.getByRole("heading", { name: "Data health" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Before trusting the rankings" })).toBeVisible();
  await expect(
    page.getByRole("listitem").filter({ hasText: "FAAB-adjusted waiver context" })
  ).toBeVisible();
  await expect(
    page.getByRole("definition").filter({ hasText: "FAAB context unavailable" })
  ).toBeVisible();
  await expect(page.getByText("25", { exact: true })).toBeVisible();
  await expect(page.getByText("2026 excluded", { exact: true })).toBeVisible();

  await page.screenshot({
    path: "../../.omo/evidence/task-8-9-playwright/data-health-withheld-score.png",
    fullPage: true
  });
});
