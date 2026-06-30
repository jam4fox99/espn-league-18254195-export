import { expect, test } from "@playwright/test";
import { installAlphaSession, mockProductApi, testLeagueUuid } from "./api-mocks";

const recordsPayload = {
  modelName: "records",
  modelVersion: "current",
  rows: [
    {
      recordId: "highest_weekly_score:2021:8",
      category: "highest_weekly_score",
      label: "Highest weekly score",
      value: 218.72,
      managerName: "Jordan Gruber",
      teamName: "Kirkumcised Penix",
      season: 2021
    },
    {
      recordId: "lineup_efficiency_leader:2022:3",
      category: "lineup_efficiency_leader",
      label: "Lineup efficiency leader",
      value: 96.4,
      managerName: "Riley Morgan",
      teamName: "The Kill",
      season: 2022
    },
    {
      // All-time superlative: spans every season, so `season` is null (not just
      // absent). The parser must accept null here — regression guard for the
      // live record-book parse failure.
      recordId: "superlative:waiver_value_leader",
      category: "waiver_value_leader",
      label: "Waiver Value Leader",
      value: 8739.72,
      managerName: "Gus Koven",
      teamName: "Maya R",
      season: null
    }
  ]
};

test("record book groups superlatives with their receipts", async ({ page }) => {
  await mockProductApi(page);
  await page.route(`**/v1/leagues/${testLeagueUuid}/records*`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(recordsPayload)
    });
  });
  await installAlphaSession(page);

  await page.goto(`/leagues/${testLeagueUuid}/record-book`);

  await expect(page.getByRole("heading", { name: "League record book" })).toBeVisible();
  await expect(page.getByText("Scoring", { exact: true })).toBeVisible();
  await expect(page.getByText("Lineups", { exact: true })).toBeVisible();
  await expect(page.getByText("218.72")).toBeVisible();
  await expect(page.getByText(/Jordan Gruber · Kirkumcised Penix · 2021/)).toBeVisible();
});
