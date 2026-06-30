import { expect, test } from "@playwright/test";
import { mockConnectApi, testRunId } from "./api-mocks";

test("alpha testers can queue an ESPN import without Supabase login", async ({ page }) => {
  const fixtureLeagueId = "12345678";

  await mockConnectApi(page, "queued");

  await page.goto("/connect");
  await expect(page.getByRole("heading", { name: "Connect ESPN league" })).toBeVisible();
  await expect(page.getByText("Supabase login")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Accept invite" })).toHaveCount(0);
  await page.getByLabel("ESPN league ID").fill(fixtureLeagueId);
  await page.getByLabel("SWID").fill("{TEST-SWID}");
  await page.getByLabel("espn_s2").fill("test-token");
  await page.getByLabel("Start season").selectOption("2020");
  await page.getByLabel("End season").selectOption("2025");
  await page.getByLabel(/I confirm this is an unofficial/).check();
  await page.getByRole("button", { name: "Start import" }).click();

  await expect(page.getByRole("status")).toContainText("Import queued");
  await expect(page.getByLabel("SWID")).toHaveValue("");
  await expect(page.getByLabel("espn_s2")).toHaveValue("");
  await page.getByRole("link", { name: new RegExp(`View run ${testRunId}`) }).click();
  await expect(page).toHaveURL(new RegExp(`/import-runs/${testRunId}`));
  await expect(page.getByText("Worker status returned without exposing artifacts.")).toBeVisible();
  await page.screenshot({
    path: "../../.omo/evidence/task-7-playwright/connect-import-success.png"
  });
});
