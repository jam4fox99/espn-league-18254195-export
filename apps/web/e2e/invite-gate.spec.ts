import { expect, test } from "@playwright/test";
import { mockProductApi, testLeagueUuid } from "./api-mocks";

test("league routes bootstrap private alpha access without Supabase login", async ({ page }) => {
  await mockProductApi(page);

  await page.goto(`/leagues/${testLeagueUuid}`);

  await expect(page).not.toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: "The story so far" })).toBeVisible();
  await expect(page.getByText("Supabase login")).toHaveCount(0);
});
