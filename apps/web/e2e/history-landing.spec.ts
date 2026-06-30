import { expect, test } from "@playwright/test";
import { installAlphaSession, mockProductApi, testLeagueUuid } from "./api-mocks";

test("league history landing shows the season timeline and champion roll", async ({ page }) => {
  await mockProductApi(page);
  await installAlphaSession(page);

  await page.goto(`/leagues/${testLeagueUuid}`);

  await expect(page.getByRole("heading", { name: "The story so far" })).toBeVisible();
  // Champion roll surfaces title holders.
  await expect(page.getByText("Jordan Lee", { exact: false }).first()).toBeVisible();
  // Completed season carries a neutral headline with a receipt; partial season is flagged.
  await expect(
    page.getByText("Jordan Lee won the championship with Waiver Cartographers")
  ).toBeVisible();
  await expect(page.getByText("In progress through week 3")).toBeVisible();

  // The Tools dropdown exposes the legacy analytics surfaces.
  await expect(page.getByRole("link", { name: "GM Ratings" })).toBeHidden();
  await page.locator(".nav-tools summary").click();
  await expect(page.getByRole("link", { name: "GM Ratings" })).toBeVisible();

  // A milestone links into the season hub.
  await page
    .getByRole("link", { name: "Jordan Lee won the championship with Waiver Cartographers" })
    .click();
  await expect(page).toHaveURL(new RegExp(`/leagues/${testLeagueUuid}/seasons/2025`));
});
