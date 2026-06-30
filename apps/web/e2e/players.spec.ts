import { expect, test } from "@playwright/test";
import { installAlphaSession, mockProductApi, testLeagueUuid } from "./api-mocks";

test("players page shows top weeks, top seasons, and efficiency leaders", async ({ page }) => {
  await mockProductApi(page);
  await installAlphaSession(page);

  await page.goto(`/leagues/${testLeagueUuid}/players`);

  await expect(page.getByRole("heading", { name: "Player leaderboards" })).toBeVisible();
  await expect(page.getByText("Top single-week performances")).toBeVisible();
  await expect(page.getByText(/Jahmyr Gibbs/)).toBeVisible();
  await expect(page.getByText("Top player-seasons")).toBeVisible();
  await expect(page.getByText(/Aaron Rodgers/)).toBeVisible();
  await expect(page.getByText("Lineup-efficiency leaders")).toBeVisible();
  await expect(page.getByText("93.4%")).toBeVisible();
});
