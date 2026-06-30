import { expect, test } from "@playwright/test";
import { installAlphaSession, mockProductApi, testLeagueUuid } from "./api-mocks";

test("rivalries matrix shows the all-play grid and nemesis table", async ({ page }) => {
  await mockProductApi(page);
  await installAlphaSession(page);

  await page.goto(`/leagues/${testLeagueUuid}/rivalries`);

  await expect(page.getByRole("heading", { name: "All-play matrix" })).toBeVisible();
  // Row header links into the franchise hub.
  await expect(page.getByRole("link", { name: /Jordan Lee/ }).first()).toBeVisible();
  // Nemesis & favorite table is present with the head-to-head edge.
  await expect(page.getByText("Nemesis & favorite opponent")).toBeVisible();
  await expect(page.getByText(/Casey Morgan \(3-7, 30%\)/)).toBeVisible();
});
