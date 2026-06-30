import { test } from "@playwright/test";
import { installAlphaSession, testLeagueUuid } from "./api-mocks";

const OUT =
  "/private/tmp/claude-501/-Users-jakemilken-Documents-MyGM/6f9aa0af-84ff-4127-a7f7-15d2801b9305/scratchpad/shots";

// Capture against the REAL local API (port 8000, demo-seeded) — no mock — so
// data-rich pages (record book, players, season hub) render their actual content.
const SURFACES: ReadonlyArray<{ readonly path: string; readonly name: string }> = [
  { path: "", name: "home" },
  { path: "/news", name: "news" },
  { path: "/history", name: "history" },
  { path: "/gms", name: "gms" },
  { path: "/players", name: "players" },
  { path: "/record-book", name: "record-book" },
  { path: "/seasons/2025", name: "season-hub" },
  { path: "/gms/espn-owner:%7BB26EFF10-1B2E-4495-B87A-998757F98DD4%7D", name: "profile" },
  { path: "/managers", name: "managers" },
  { path: "/trades", name: "trades" },
  { path: "/waivers", name: "waivers" },
  { path: "/rivalries", name: "rivalries" }
];

test("capture phase-1 surfaces", async ({ page }) => {
  test.setTimeout(180000);
  await page.setViewportSize({ width: 1280, height: 900 });
  await installAlphaSession(page);
  for (const surface of SURFACES) {
    await page.goto(`/leagues/${testLeagueUuid}${surface.path}`);
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${OUT}/${surface.name}-1280.png`, fullPage: true });
  }
});
