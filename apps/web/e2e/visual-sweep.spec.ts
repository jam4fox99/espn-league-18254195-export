import { expect, test } from "@playwright/test";
import { installAlphaSession, mockProductApi, testLeagueUuid } from "./api-mocks";

// Surfaces to sweep + a heading that proves the surface rendered.
const SURFACES: ReadonlyArray<{ readonly path: string; readonly heading: RegExp }> = [
  { path: "", heading: /Snapshot Test League|League home/ },
  { path: "/history", heading: /The story so far/ },
  { path: "/gms", heading: /GM leaderboard/ },
  { path: "/players", heading: /Player leaderboards/ },
  { path: "/managers", heading: /Franchise directory/ },
  { path: "/trades", heading: /Trade browser/ },
  { path: "/record-book", heading: /record book/i }
];

const VIEWPORTS: ReadonlyArray<{
  readonly name: string;
  readonly width: number;
  readonly height: number;
}> = [
  { name: "375", width: 375, height: 812 },
  { name: "1280", width: 1280, height: 900 }
];

for (const viewport of VIEWPORTS) {
  test(`no horizontal scroll + no broken images at ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await mockProductApi(page);
    await installAlphaSession(page);

    for (const surface of SURFACES) {
      await page.goto(`/leagues/${testLeagueUuid}${surface.path}`);
      await expect(page.getByRole("heading", { name: surface.heading }).first()).toBeVisible();

      // No horizontal scroll on any surface at any breakpoint (§9).
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth
      );
      expect(
        overflow,
        `horizontal overflow on ${surface.path} @ ${viewport.name}`
      ).toBeLessThanOrEqual(1);

      // Zero broken images: every <img> that finished loading has intrinsic size
      // (fallbacks render as inline SVG/monogram, not broken <img>). (§11)
      const broken = await page.evaluate(() =>
        Array.from(document.querySelectorAll("img"))
          .filter((img) => img.complete && img.naturalWidth === 0)
          .map((img) => img.currentSrc || img.src)
      );
      expect(broken, `broken images on ${surface.path} @ ${viewport.name}`).toEqual([]);

      await page.screenshot({
        path: `playwright-report/sweep/${surface.path.replace(/\//g, "_") || "history"}-${viewport.name}.png`,
        fullPage: true
      });
    }
  });
}

test("reduced-motion resolves animations to their final state", async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: "reduce" });
  const page = await context.newPage();
  await mockProductApi(page);
  await installAlphaSession(page);
  await page.goto(`/leagues/${testLeagueUuid}/gms`);
  await expect(page.getByRole("heading", { name: /GM leaderboard/ })).toBeVisible();

  // The OVR ring arc reaches its final swept offset (not the empty full
  // circumference) even with motion reduced.
  const arc = page.locator(".ovr-ring__arc").first();
  await expect(arc).toHaveCount(1);
  const offsetReached = await arc.evaluate((node) => {
    const circle = node as unknown as SVGCircleElement;
    const offset = Number.parseFloat(circle.getAttribute("stroke-dashoffset") ?? "0");
    const dash = Number.parseFloat(circle.getAttribute("stroke-dasharray") ?? "0");
    return offset < dash; // arc has swept in
  });
  expect(offsetReached).toBe(true);
  await context.close();
});
