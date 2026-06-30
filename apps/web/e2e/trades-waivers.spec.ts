import { mkdirSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { installAlphaSession, mockProductApi, testLeagueUuid } from "./api-mocks";

const evidenceDir = "../../.omo/evidence/task-10-mygm-espn-full-dashboard";

test("browses trades and waivers with filters, players, and caveats", async ({ page }) => {
  mkdirSync(evidenceDir, { recursive: true });
  await mockProductApi(page);
  await installAlphaSession(page);

  // Trades render as manager-vs-manager analyzer cards with players and grades.
  await page.goto(`/leagues/${testLeagueUuid}/trades`);
  await expect(page.getByRole("heading", { name: "Trade browser" })).toBeVisible();
  await expect(page.getByText("Jordan Lee").first()).toBeVisible();
  await expect(page.getByText("Deebo Samuel")).toBeVisible();
  await expect(page.getByText("A+").first()).toBeVisible();

  await page.getByLabel("View").selectOption("manager");
  await expect(page.getByText("No manager claim is available here")).toBeVisible();
  await page.getByLabel("Manager or team").selectOption("espn-owner:alpha");
  await expect(page.getByText("Deebo Samuel")).toBeVisible();

  await page.getByLabel("View").selectOption("best");
  await expect(page.getByText("+31.4").first()).toBeVisible();

  await page.screenshot({ path: `${evidenceDir}/trades-waivers.png`, fullPage: true });

  // Waivers render as add/drop rows with player chips.
  await page.goto(`/leagues/${testLeagueUuid}/waivers`);
  await expect(page.getByRole("heading", { name: "Waiver and free-agent browser" })).toBeVisible();
  await page.getByLabel("Transaction type").selectOption("FREEAGENT");
  await expect(page.getByText("Streaming TE").first()).toBeVisible();
  await page.getByLabel("Transaction type").selectOption("all");
  await page.getByLabel("View").selectOption("best-pickups");
  await expect(page.getByText("Tank Dell").first()).toBeVisible();
  await page.getByLabel("View").selectOption("worst-drops");
  await expect(page.getByText("Breakout WR").first()).toBeVisible();

  // Selecting a caveated move opens its detail with the exclusion caveat.
  await page.getByLabel("View").selectOption("all");
  await page.getByLabel("Transaction type").selectOption("FREEAGENT");
  await page.getByRole("button").filter({ hasText: "Streaming TE" }).first().click();
  await expect(page.getByText("Missing add/drop point rows")).toBeVisible();
  await expect(page.getByText("Unresolved Player 882").first()).toBeVisible();

  await page.screenshot({ path: `${evidenceDir}/transaction-caveat.png`, fullPage: true });
});
