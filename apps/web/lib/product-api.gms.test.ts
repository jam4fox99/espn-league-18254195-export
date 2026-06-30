import { describe, expect, it } from "vitest";
import { parseAnalyticsPayload, parseManagerReportPayload } from "@/lib/product-api";

// The live /gms and /seasons endpoints return the snapshot-rows envelope
// ({modelName, modelVersion, rows}) without top-level confidence/sourceCoverage.
// Before the fix this fell through to fixturePayloadSchema.parse and threw
// "expected object, path: dashboard".
const gmsPayload = {
  modelName: "leaderboard",
  modelVersion: "351761c7-7df5-42f4-b875-cc73d5c96cf2",
  rows: [
    {
      rank: 1,
      managerKey: "espn-owner:{B618B4FC-D3B6-4CD9-B75F-7FC4924DC93B}",
      managerName: "Emmett Slavin",
      displayName: "Emmett Slavin",
      teamName: "Mixon's Right Hook",
      score: 74.3086,
      confidence: "low",
      season: null,
      componentBreakdown: {
        luckAdjusted: { label: "Luck-adjusted", value: 100 },
        tradePerformance: { label: "Trade performance", value: 73.68 }
      },
      caveats: ["2026 excluded from career ratings by default"]
    }
  ]
};

describe("GM leaderboard snapshot-rows parsing", () => {
  it("parses the snapshot-rows envelope without throwing and exposes manager names", () => {
    const data = parseAnalyticsPayload(gmsPayload, "v1/leagues/abc/gms");
    const leaderboardRow = data.rows[0]?.leaderboard?.[0];
    expect(leaderboardRow?.managerName).toBe("Emmett Slavin");
    expect(leaderboardRow?.teamName).toBe("Mixon's Right Hook");
    expect(leaderboardRow?.score).toBe(74.3086);
  });
});

describe("Manager report card parsing", () => {
  it("surfaces the enriched score and component breakdown from the profile endpoint", () => {
    const report = parseManagerReportPayload(
      {
        managerKey: "espn-owner:{B618B4FC-D3B6-4CD9-B75F-7FC4924DC93B}",
        displayName: "Emmett Slavin",
        teamAliases: [{ season: 2022, teamId: 9, teamName: "Mixon's Right Hook" }],
        scoreEligible: true,
        caveats: [],
        compositeScore: 74.3086,
        confidence: "low",
        componentBreakdown: {
          tradePerformance: { label: "Trade performance", value: 73.68 }
        }
      },
      "abc",
      "espn-owner:{B618B4FC-D3B6-4CD9-B75F-7FC4924DC93B}"
    );
    expect(report.compositeScore).toBe(74.3086);
    expect(report.managerName).toBe("Emmett Slavin");
    expect(Object.keys(report.componentBreakdown)).toContain("tradePerformance");
  });
});
