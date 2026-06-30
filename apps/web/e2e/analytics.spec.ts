import { expect, test } from "@playwright/test";
import { installAlphaSession, mockProductApi, testLeagueUuid, testManagerId } from "./api-mocks";

test("authenticated league analytics show retrospective facts and route coverage", async ({
  page
}) => {
  await mockProductApi(page);
  await installAlphaSession(page);

  await page.goto(`/leagues/${testLeagueUuid}/overview`);
  await expect(page.getByRole("heading", { name: "Snapshot Test League" })).toBeVisible();
  await expect(page.getByText("All-time leaderboard", { exact: true })).toBeVisible();
  await expect(page.getByText("2025, 2026")).toBeVisible();
  await expect(page.locator("body")).toContainText("2026 excluded from career ratings");
  await page.getByRole("button", { name: "Recompute snapshot" }).click();
  await expect(page.getByText("Status: queued · recompute requested")).toBeVisible();

  await page.goto(`/leagues/${testLeagueUuid}/gms`);
  await expect(page.getByRole("heading", { name: "GM leaderboard" })).toBeVisible();
  // 2K board: GM name promotes into the in-page hero (button); the hero carries
  // the "View franchise" CTA. Caveats are collapsed on the showcase (decision 4).
  await expect(page.getByText("Riley Morgan").first()).toBeVisible();
  await expect(page.getByRole("link", { name: /View franchise/ })).toBeVisible();
  await page.screenshot({
    path: "../../.omo/evidence/task-9-mygm-espn-full-dashboard/dashboard-gms.png",
    fullPage: true
  });

  await page.goto(`/leagues/${testLeagueUuid}/gms/${encodeURIComponent(testManagerId)}`);
  await expect(page.getByText("Riley Morgan")).toBeVisible();
  await expect(page.getByText("Trade performance")).toBeVisible();
  await expect(page.getByText(/35%/).first()).toBeVisible();
  await expect(
    page.getByText("Trade component withheld: no gradable trades").first()
  ).toBeVisible();
  await page.screenshot({
    path: "../../.omo/evidence/task-9-mygm-espn-full-dashboard/manager-caveat.png",
    fullPage: true
  });

  await page.goto(`/leagues/${testLeagueUuid}/overview`);
  await expect(page.getByRole("link", { name: /Compare GMs/ })).toBeVisible();
});
