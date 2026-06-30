import { mkdirSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { installAlphaSession, mockProductApi, testLeagueUuid, testManagerId } from "./api-mocks";

const evidenceDir =
  process.env["MYGM_EVIDENCE_DIR"] ??
  "../../.omo/evidence/task-12-mygm-espn-full-dashboard/full-dashboard";

test("navigates the full ESPN snapshot dashboard flow", async ({ page }) => {
  mkdirSync(evidenceDir, { recursive: true });
  await mockProductApi(page);
  await installAlphaSession(page);

  await page.goto(`/leagues/${testLeagueUuid}/overview`);
  await expect(page.getByRole("heading", { name: "Snapshot Test League" })).toBeVisible();
  await page.getByRole("button", { name: "Recompute snapshot" }).click();
  await expect(page.getByText("Status: queued · recompute requested")).toBeVisible();
  await page.screenshot({ path: `${evidenceDir}/dashboard-main.png`, fullPage: true });

  await page.getByRole("link", { name: "Compare GMs" }).click();
  await expect(page.getByRole("heading", { name: "GM leaderboard" })).toBeVisible();
  await page.screenshot({ path: `${evidenceDir}/gm-leaderboard.png`, fullPage: true });
  // 2K board: clicking a GM row promotes it into the hero, whose "View
  // franchise" CTA links into the Franchise Hub.
  await page.getByRole("button", { name: /Riley Morgan/ }).click();
  await expect(page.getByRole("link", { name: /View franchise/ })).toBeVisible();
  // Caveats are collapsed on the showcase; the manager report card carries them.
  await page.goto(`/leagues/${testLeagueUuid}/gms/${encodeURIComponent(testManagerId)}`);
  await expect(page.getByText("Riley Morgan").first()).toBeVisible();
  await expect(
    page.getByText("Trade component withheld: no gradable trades").first()
  ).toBeVisible();
  await page.screenshot({ path: `${evidenceDir}/gm-profile-caveats.png`, fullPage: true });

  await page.goto(`/leagues/${testLeagueUuid}/trades`);
  await expect(page.getByRole("heading", { name: "Trade browser" })).toBeVisible();
  await page.getByLabel("View").selectOption("best");
  await expect(page.getByText("Deebo Samuel").first()).toBeVisible();
  await page.screenshot({ path: `${evidenceDir}/trades-browser.png`, fullPage: true });

  await page.goto(`/leagues/${testLeagueUuid}/waivers`);
  await expect(page.getByRole("heading", { name: "Waiver and free-agent browser" })).toBeVisible();
  await page.getByLabel("View").selectOption("worst-drops");
  await expect(page.getByText("Breakout WR").first()).toBeVisible();
  await page.screenshot({ path: `${evidenceDir}/waivers-browser.png`, fullPage: true });

  await page.goto(`/leagues/${testLeagueUuid}/records`);
  await expect(page.getByRole("heading", { name: "League records" })).toBeVisible();
  await expect(page.getByText("Top retrospective score")).toBeVisible();
  await page.screenshot({ path: `${evidenceDir}/records.png`, fullPage: true });

  // Head-to-Head now redirects into Rivalries (mygm-fixes goal, Phase 5).
  await page.goto(`/leagues/${testLeagueUuid}/rivalries`);
  await expect(page.getByRole("heading", { name: "All-play matrix" })).toBeVisible();
  await page.screenshot({ path: `${evidenceDir}/rivalries.png`, fullPage: true });

  await page.goto(`/leagues/${testLeagueUuid}/data-health`);
  await expect(page.getByRole("heading", { name: "Data health" })).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "Score exclusion reasons" })).toBeVisible();
  await page.screenshot({ path: `${evidenceDir}/data-health.png`, fullPage: true });

  await page.goto(`/leagues/${testLeagueUuid}/formula`);
  await expect(page.getByRole("heading", { name: "Formula and provenance" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Excluded" })).toBeVisible();
  await page.screenshot({ path: `${evidenceDir}/full-dashboard-flow.png`, fullPage: true });
});
