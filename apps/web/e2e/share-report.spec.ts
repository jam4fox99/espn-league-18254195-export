import { expect, test } from "@playwright/test";
import { installAlphaSession, mockProductApi, testLeagueUuid, testShareSlug } from "./api-mocks";

test("share management creates privacy-safe public report without internal ids", async ({
  page
}) => {
  await mockProductApi(page);
  await installAlphaSession(page);

  await page.goto(`/leagues/${testLeagueUuid}/settings`);
  await expect(page.getByRole("heading", { name: "Share management" })).toBeVisible();
  await expect(page.getByRole("link", { name: `/s/${testShareSlug}` })).toBeVisible();
  await page.getByRole("button", { name: "Create share" }).click();
  await expect(page.getByRole("status")).toContainText("Privacy-safe share link created");

  await page.goto(`/s/${testShareSlug}`);
  await expect(page.getByText("Jordan Lee")).toBeVisible();
  await expect(page.getByText("Retrospective GM Rating")).toBeVisible();
  await expect(page.getByText("2026 excluded from career ratings")).toBeVisible();

  const bodyText = await page.locator("body").innerText();
  expect(bodyText).not.toContain(testLeagueUuid);
  expect(bodyText).not.toContain("managerId");
  expect(bodyText).not.toContain("versionId");
  expect(bodyText).not.toContain("shareLinkId");
  expect(bodyText).not.toContain("espn_s2");
  expect(bodyText).not.toContain("raw-imports");
  expect(bodyText).not.toContain("derived-artifacts");

  await page.screenshot({
    path: "../../.omo/evidence/task-8-9-playwright/share-report.png",
    fullPage: true
  });
});
