import { describe, expect, it } from "vitest";
import * as productApi from "./product-api";
import {
  parseAnalyticsPayload,
  parseDashboardPayload,
  parseLeagueAnalyticsSnapshot,
  parseManagerReportPayload
} from "./product-api";

const leagueId = "11111111-1111-4111-8111-111111111111";

describe("product API payload parsing", () => {
  it("accepts the ESPN league analytics snapshot contract", () => {
    const dashboard = parseDashboardPayload(snapshotPayload(), leagueId);

    expect(productApi).toHaveProperty("parseLeagueAnalyticsSnapshot");
    expect(dashboard.productLabel).toBe("Retrospective GM Rating");
    expect(dashboard.leagueName).toBe("Fixture League");
    expect(dashboard.availableSeasons).toEqual([2025]);
    expect(dashboard.leaderboard?.[0]?.managerKey).toBe("espn-owner:owner-1");
    expect(dashboard.careerExcludedSeasons).toEqual([2026]);
    expect(dashboard.counts?.canonicalTradeEvents).toBe(1);
    expect(dashboard.counts?.waiverRows).toBe(1);
    expect(dashboard.caveats).toContain("FAAB context unavailable");
  });

  it("allows snapshot rows to include API-specific detail fields", () => {
    const snapshot = parseLeagueAnalyticsSnapshot(snapshotPayload(), leagueId);

    expect(snapshot.managers[0]?.components?.["tradePerformance"]?.score).toBe(91.2);
    expect(snapshot.leaderboards.allTime[0]?.componentBreakdown?.["tradePerformance"]?.score).toBe(
      91.2
    );
    expect(snapshot.trades.items[0]?.["netPoints"]).toBe(14.5);
  });

  it("keeps unavailable manager components caveated without fabricating a score", () => {
    const report = parseManagerReportPayload(
      managerProfilePayload(),
      leagueId,
      "espn-owner:owner-2"
    );

    expect(report.managerKey).toBe("espn-owner:owner-2");
    expect(report.componentBreakdown["tradePerformance"]?.score).toBeNull();
    expect(report.componentBreakdown["tradePerformance"]?.caveats).toContain(
      "Trade component withheld: no gradable trades"
    );
    expect(report.caveats).toContain("Trade component withheld: no gradable trades");
  });

  it("normalizes the deployed flat dashboard payload into ready fixture facts", () => {
    const dashboard = parseDashboardPayload(
      {
        leagueId,
        version: "current",
        payloadVersion: "mygm-fixture-dashboard-v1",
        productLabel: "Retrospective GM Rating",
        importStatus: "queued",
        compositeScore: 79.4449,
        sourceCounts: {
          seasons: 7,
          playerWeekRows: 28294,
          waiverRows: 2662,
          freeAgentRows: 1237,
          executedAcceptedTrades: 95,
          gradedTradeRows: 70,
          canonicalTradeEvents: 51
        },
        careerExcludedSeasons: [2026]
      },
      leagueId
    );

    expect(dashboard.counts?.canonicalTradeEvents).toBe(51);
    expect(dashboard.counts?.ungradedExecutedAccepts).toBe(25);
    expect(dashboard.counts?.waiverRows).toBe(2662);
    expect(dashboard.counts?.freeAgentRows).toBe(1237);
    expect(dashboard.faabContext).toBe("FAAB context unavailable: bidAmount is always 0");
    expect(dashboard.careerExcludedSeasons).toEqual([2026]);
  });

  it("normalizes API analytics row collections instead of requiring fixture payloads", () => {
    const analytics = parseAnalyticsPayload(
      {
        modelName: "trade_outcome_v1",
        modelVersion: "current",
        confidence: "fixture",
        sourceCoverage: "local-fixture-contract",
        rows: [
          {
            label: "Retrospective GM Rating",
            value: 70,
            counts: {
              executedAcceptedTrades: 95,
              gradedTradeRows: 70,
              canonicalTradeEvents: 51
            },
            caveats: ["current uses local fixture-backed analytics"]
          }
        ]
      },
      `v1/leagues/${leagueId}/trades?version=current`
    );

    expect(analytics.rows[0]?.leagueId).toBe(leagueId);
    expect(analytics.rows[0]?.compositeScore).toBe(70);
    expect(analytics.rows[0]?.counts?.canonicalTradeEvents).toBe(51);
    expect(analytics.rows[0]?.counts?.ungradedExecutedAccepts).toBe(25);
    expect(analytics.rows[0]?.faabContext).toBe("FAAB context unavailable: bidAmount is always 0");
  });
});

function snapshotPayload() {
  return {
    meta: {
      snapshotVersion: "espn-league-analytics-snapshot-v1",
      source: "espn",
      generatedAt: "fixture-contract",
      productLabel: "Retrospective GM Rating",
      formulaVersion: "mygm-retrospective-v1",
      importStatus: "available"
    },
    league: {
      leagueId,
      name: "Fixture League",
      platform: "espn"
    },
    seasons: [{ season: 2025, finalWeek: 14, isPartial: false }],
    managers: [
      {
        managerKey: "espn-owner:owner-1",
        displayName: "Manager One",
        scoreEligible: true,
        caveats: [],
        teamAliases: [{ season: 2025, teamId: 1, teamName: "Fixture First" }],
        components: {
          tradePerformance: {
            label: "Trade performance",
            score: 91.2,
            weight: 0.35,
            caveats: []
          }
        }
      },
      {
        managerKey: "espn-owner:owner-2",
        displayName: "Manager Two",
        scoreEligible: true,
        caveats: []
      }
    ],
    leaderboards: {
      allTime: [
        {
          rank: 1,
          managerKey: "espn-owner:owner-1",
          score: 87.5,
          confidence: "high",
          componentBreakdown: {
            tradePerformance: {
              label: "Trade performance",
              score: 91.2,
              weight: 0.35,
              caveats: []
            }
          }
        }
      ],
      bySeason: []
    },
    trades: {
      items: [
        {
          tradeId: "trade-1",
          season: 2025,
          managerKeys: ["espn-owner:owner-1", "espn-owner:owner-2"],
          scoreEligible: false,
          caveats: ["contract fixture trade row"],
          netPoints: 14.5
        }
      ]
    },
    waivers: {
      items: [
        {
          moveId: "waiver-1",
          season: 2025,
          managerKey: "espn-owner:owner-1",
          transactionType: "WAIVER",
          scoreEligible: false,
          caveats: ["FAAB context unavailable"]
        }
      ]
    },
    records: {
      items: [
        {
          recordId: "highest-weekly-score",
          category: "weeklyScore",
          label: "Highest weekly score",
          value: 161.2,
          managerKey: "espn-owner:owner-1"
        }
      ]
    },
    headToHead: {
      pairs: [
        {
          pairId: "owner-1-owner-2",
          managerAKey: "espn-owner:owner-1",
          managerBKey: "espn-owner:owner-2",
          matchups: [],
          caveats: ["contract fixture pair"]
        }
      ]
    },
    dataHealth: {
      status: "caveated",
      caveats: ["FAAB context unavailable"],
      warnings: ["partial season excluded"],
      withheldScores: ["FAAB-adjusted waiver context"]
    },
    formula: {
      formulaVersion: "mygm-retrospective-v1",
      provenance: "fixture-derived ESPN export analytics",
      weights: {
        tradePerformance: 0.35,
        waiverPerformance: 0.35,
        recordAndPoints: 0.2,
        luckAdjusted: 0.1
      }
    }
  };
}

function managerProfilePayload() {
  return {
    managerKey: "espn-owner:owner-2",
    displayName: "Manager Two",
    teamAliases: [{ season: 2025, teamId: 2, teamName: "Fixture Second" }],
    scoreEligible: false,
    caveats: ["Trade component withheld: no gradable trades"],
    componentBreakdown: {
      tradePerformance: {
        label: "Trade performance",
        score: null,
        weight: 0.35,
        caveats: ["Trade component withheld: no gradable trades"]
      },
      waiverPerformance: {
        label: "Waiver performance",
        score: 72.4,
        weight: 0.35,
        caveats: []
      }
    },
    allTimeStats: {
      seasons: 1,
      wins: 7,
      losses: 7,
      pointsFor: 1788.4
    },
    bestMoves: [{ label: "Best pickup", detail: "Added RB depth", value: 21.4 }],
    worstMoves: []
  };
}
