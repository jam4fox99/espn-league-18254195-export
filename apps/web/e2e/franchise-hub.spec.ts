import { expect, test } from "@playwright/test";
import { installAlphaSession, mockProductApi, testLeagueUuid } from "./api-mocks";

test("franchise directory links into a manager hub with career, eras, and rivalries", async ({
  page
}) => {
  await mockProductApi(page);
  await installAlphaSession(page);

  await page.goto(`/leagues/${testLeagueUuid}/managers`);
  await expect(page.getByRole("heading", { name: "Franchise directory" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Jordan Lee" })).toBeVisible();

  await page.getByRole("link", { name: "Jordan Lee" }).click();
  await expect(page).toHaveURL(/\/managers\/espn-owner%3Aowner-1/);

  // Career header + aggregated sections.
  await expect(page.getByRole("heading", { name: "Jordan Lee" })).toBeVisible();
  await expect(page.getByText("Career GM rating")).toBeVisible();
  await expect(page.getByText("Top-3 finishes 2023-2024, 2 titles")).toBeVisible();
  // Written trade + waiver summaries are surfaced neutrally.
  await expect(page.getByText("2024: acquired Jahmyr Gibbs")).toBeVisible();
  await expect(page.getByText("2024: added Tank Dell")).toBeVisible();
  // Nemesis / favorite split.
  await expect(page.getByText("Nemesis")).toBeVisible();
  await expect(page.getByText("Favorite opponent")).toBeVisible();
});
