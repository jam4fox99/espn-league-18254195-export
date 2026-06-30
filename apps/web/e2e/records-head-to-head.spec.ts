import { expect, type Page, type Route, test } from "@playwright/test";
import { installAlphaSession, testLeagueUuid } from "./api-mocks";

const managerAKey = "espn-owner:alice";
const managerBKey = "espn-owner:blake";

test("records, head-to-head, data-health, and formula surfaces show caveated snapshot data", async ({
  page
}) => {
  await mockRecordsHeadToHeadApi(page);
  await installAlphaSession(page);

  await page.goto(`/leagues/${testLeagueUuid}/records`);
  await expect(page.getByRole("heading", { name: "League records" })).toBeVisible();
  await expect(page.getByText("Highest weekly score")).toBeVisible();
  await expect(page.getByText("Largest matchup margin")).toBeVisible();
  await expect(page.getByText("Championship counts and playoff splits")).toBeVisible();

  // Head-to-Head is retired in favour of Rivalries (mygm-fixes goal, Phase 5); the
  // per-pair record now lives in the all-play matrix, covered by rivalries.spec.ts.

  await page.goto(`/leagues/${testLeagueUuid}/data-health`);
  await expect(page.getByText("Unresolved players")).toBeVisible();
  await expect(page.getByText("Incomplete trades")).toBeVisible();
  await expect(page.getByText("Missing point rows")).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "Score exclusion reasons" })).toBeVisible();

  await page.goto(`/leagues/${testLeagueUuid}/formula`);
  await expect(page.getByText("Trade performance")).toBeVisible();
  await expect(page.getByText("35%")).toHaveCount(2);
  await expect(page.getByText("Record and points-for")).toBeVisible();
  await expect(page.getByText("Draft grade")).toBeVisible();
  await expect(page.getByRole("cell", { name: "Excluded" })).toBeVisible();
  await page.screenshot({
    path: "../../.omo/evidence/task-11-mygm-espn-full-dashboard/unsupported-fields.png",
    fullPage: true
  });
});

async function mockRecordsHeadToHeadApi(page: Page): Promise<void> {
  await page.route("http://127.0.0.1:8000/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const pathname = url.pathname;

    if (pathname === `/v1/leagues/${testLeagueUuid}/records`) {
      await json(route, {
        modelName: "records_v1",
        modelVersion: "mygm-retrospective-v1",
        rows: [
          {
            recordId: "highest-weekly-score",
            category: "weekly_score",
            label: "Highest weekly score",
            value: 142.6,
            managerKey: managerAKey,
            season: 2025,
            detail: "Week 4"
          },
          {
            recordId: "largest-matchup-margin",
            category: "matchup",
            label: "Largest matchup margin",
            value: 23.4,
            managerKey: managerAKey,
            season: 2025,
            detail: "Alice Carter over Blake Singh",
            caveats: ["Playoff/championship fields omitted: source snapshot has no playoff marker."]
          }
        ]
      });
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/gms`) {
      await json(route, {
        modelName: "career_gm_rating_v1",
        modelVersion: "mygm-retrospective-v1",
        rows: [
          { managerKey: managerAKey, displayName: "Alice Carter" },
          { managerKey: managerBKey, displayName: "Blake Singh" }
        ]
      });
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/head-to-head`) {
      await json(route, {
        pairs: [
          {
            pairId: "alice-blake",
            managerAKey,
            managerBKey,
            managerADisplayName: "Alice Carter",
            managerBDisplayName: "Blake Singh",
            managerAWins: 1,
            managerBWins: 0,
            ties: 0,
            averageScore: 130.9,
            biggestWin: "Alice Carter by 23.4",
            streak: "Alice Carter W1",
            caveats: ["Playoff split omitted: source matchups do not mark playoff games."],
            matchups: [
              {
                season: 2025,
                week: 4,
                winnerKey: managerAKey,
                scoreSummary: "Alice Carter 142.6 - Blake Singh 119.2"
              }
            ]
          }
        ]
      });
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/data-health`) {
      await json(route, {
        modelName: "data_health_v1",
        warnings: [
          "25 ungraded executed accepts visible",
          "Missing point rows exclude affected waiver scores"
        ],
        withheldScores: ["FAAB-adjusted waiver context", "Incomplete trade grades"],
        caveats: [
          "FAAB context unavailable: bidAmount is always 0",
          "2026 excluded from career ratings"
        ],
        ungradedExecutedAccepts: 25,
        faabContext: "FAAB context unavailable: bidAmount is always 0",
        careerExcludedSeasons: [2026]
      });
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/formula`) {
      await json(route, {
        scoreModels: ["trade_outcome", "waiver_efficiency", "record_points", "luck_adjusted"],
        caveat: "Draft excluded unless real draft and ADP data exist",
        provenance: "fixture-derived ESPN export analytics",
        formulaVersion: "mygm-retrospective-v1"
      });
      return;
    }

    await json(route, { detail: "unhandled records/head-to-head mock route" }, 404);
  });
}

async function json(route: Route, body: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body)
  });
}
