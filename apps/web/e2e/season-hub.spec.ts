import { expect, test } from "@playwright/test";
import { installAlphaSession, mockProductApi, testLeagueUuid } from "./api-mocks";

test("season hub shows the review, standings, and draft recap", async ({ page }) => {
  await mockProductApi(page);
  await installAlphaSession(page);

  await page.goto(`/leagues/${testLeagueUuid}/seasons/2025`);

  await expect(page.getByRole("heading", { name: "2025 season" })).toBeVisible();
  // Season-in-review narrative.
  await expect(
    page.getByText("Jordan Lee won the championship with Waiver Cartographers (11-3).")
  ).toBeVisible();
  // Final standings table.
  await expect(page.getByText("Final standings")).toBeVisible();
  await expect(page.getByText("Caveat Crew")).toBeVisible();
  // Draft recap with steal + bust.
  await expect(page.getByText("Steal of the draft")).toBeVisible();
  await expect(page.getByText("Tank Dell")).toBeVisible();
  await expect(page.getByText("Biggest bust")).toBeVisible();
});
