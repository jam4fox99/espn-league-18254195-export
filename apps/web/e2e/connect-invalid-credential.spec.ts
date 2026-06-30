import { expect, test } from "@playwright/test";
import { mockConnectApi } from "./api-mocks";

test("invalid ESPN credentials render an error on connect", async ({ page }) => {
  await mockConnectApi(page, "credential-error");

  await page.goto("/connect");
  await page.getByLabel("ESPN league ID").fill("123456");
  await page.getByLabel("SWID").fill("{TEST-SWID}");
  await page.getByLabel("espn_s2").fill("invalid-token");
  await page.getByLabel(/I confirm this is an unofficial/).check();
  await page.getByRole("button", { name: "Start import" }).click();

  await expect(
    page.getByText("Credential validation failed. Check ESPN cookies and try again.")
  ).toBeVisible();
  await expect(page.getByLabel("SWID")).toHaveValue("");
  await expect(page.getByLabel("espn_s2")).toHaveValue("");
});
