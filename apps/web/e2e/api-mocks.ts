import type { Page, Route } from "@playwright/test";

export const testLeagueUuid = "11111111-1111-4111-8111-111111111111";
export const testRunId = "22222222-2222-4222-8222-222222222222";
export const testReprocessRunId = "33333333-3333-4333-8333-333333333333";
export const testManagerId = "espn-owner:owner-2";
export const testVersionId = "44444444-4444-4444-8444-444444444444";
export const testShareLinkId = "55555555-5555-4555-8555-555555555555";
export const testShareSlug = "privacy-safe-alpha";
export const testTradeId = "trade-2025-01";
export const testCaveatedTradeId = "trade-2025-caveat";
export const testWaiverId = "move-2025-01";
export const testCaveatedWaiverId = "move-2025-caveat";

export async function mockConnectApi(page: Page, outcome: "queued" | "credential-error") {
  await page.route("http://127.0.0.1:8000/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;

    if (pathname === "/v1/alpha-invites/accept") {
      await json(route, 200, { status: "accepted" });
      return;
    }

    if (pathname === "/v1/leagues" && request.method() === "POST") {
      await json(route, 201, { league_id: testLeagueUuid });
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/credentials/validate`) {
      await json(
        route,
        outcome === "credential-error" ? 401 : 200,
        outcome === "credential-error" ? { detail: "invalid credentials" } : { status: "valid" }
      );
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/credentials`) {
      await json(route, 200, { credentialVersion: 1 });
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/import-runs`) {
      await json(route, 202, { run_id: testRunId });
      return;
    }

    if (pathname === `/v1/import-runs/${testRunId}`) {
      await json(route, 200, {
        runId: testRunId,
        leagueId: testLeagueUuid,
        status: "queued",
        step: "fetch_core",
        credentialVersion: 1,
        warnings: []
      });
      return;
    }

    await json(route, 404, { detail: "unhandled mock route" });
  });
}

export async function mockProductApi(page: Page) {
  const snapshot = snapshotProductPayload();
  const fixtureProductPayload = productFixturePayload();

  await page.route("http://127.0.0.1:8000/v1/**", async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;

    if (pathname === `/v1/leagues/${testLeagueUuid}/dashboard`) {
      await json(route, 200, snapshot);
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/history`) {
      await json(route, 200, historyPayload());
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/managers`) {
      await json(route, 200, managerDirectoryPayload());
      return;
    }

    if (
      decodeURIComponent(pathname) === `/v1/leagues/${testLeagueUuid}/managers/espn-owner:owner-1`
    ) {
      await json(route, 200, managerHubPayload());
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/seasons/2025/hub`) {
      await json(route, 200, seasonHubPayload());
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/rivalries`) {
      await json(route, 200, rivalriesPayload());
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/players/leaderboards`) {
      await json(route, 200, playerLeaderboardsPayload());
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/reprocess-runs`) {
      const body = request.postDataJSON() as {
        sourceImportRunId?: string;
        targets?: readonly string[];
        formulaVersion?: string;
      };
      if (
        request.method() !== "POST" ||
        body.sourceImportRunId !== testRunId ||
        body.formulaVersion !== "mygm-retrospective-v1" ||
        body.targets?.[0] !== "analyticsSnapshot" ||
        body.targets.length !== 1
      ) {
        await json(route, 422, { detail: "invalid recompute body" });
        return;
      }
      await json(route, 202, reprocessRun());
      return;
    }

    if (pathname === `/v1/reprocess-runs/${testReprocessRunId}`) {
      await json(route, 200, reprocessRun());
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/seasons/2025`) {
      await json(route, 200, fixtureProductPayload);
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/gms`) {
      await json(route, 200, {
        modelName: "career_gm_rating_v1",
        modelVersion: "mygm-retrospective-v1",
        confidence: "snapshot",
        sourceCoverage: "published ESPN analytics snapshot",
        rows: snapshot.leaderboards.allTime.map((row) => ({
          ...row,
          label: row.displayName,
          value: row.score
        }))
      });
      return;
    }

    if (decodeURIComponent(pathname) === `/v1/leagues/${testLeagueUuid}/gms/${testManagerId}`) {
      await json(route, 200, {
        managerKey: testManagerId,
        version: "mygm-retrospective-v1",
        compositeScore: null,
        confidence: "caveated",
        displayName: "Riley Morgan",
        teamAliases: [{ season: 2025, teamId: 2, teamName: "Caveat Crew" }],
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
        bestMoves: [{ label: "Best pickup", detail: "Added RB depth", value: 21.4 }],
        worstMoves: []
      });
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/trades/${testTradeId}`) {
      await json(route, 200, { item: tradeRows()[0] });
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/trades/${testCaveatedTradeId}`) {
      await json(route, 200, { item: tradeRows()[1] });
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/trades`) {
      await json(route, 200, {
        modelName: "trades",
        modelVersion: testVersionId,
        rows: tradeRows()
      });
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/waivers/${testWaiverId}`) {
      await json(route, 200, { item: waiverRows()[0] });
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/waivers/${testCaveatedWaiverId}`) {
      await json(route, 200, { item: waiverRows()[1] });
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/waivers`) {
      await json(route, 200, {
        modelName: "waivers",
        modelVersion: testVersionId,
        rows: waiverRows()
      });
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/records`) {
      await json(route, 200, fixtureProductPayload);
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/head-to-head`) {
      await json(route, 200, {
        pairs: [
          {
            pairId: "owner-1-owner-2",
            managerAKey: "espn-owner:owner-1",
            managerBKey: testManagerId,
            managerADisplayName: "Jordan Lee",
            managerBDisplayName: "Riley Morgan",
            managerAWins: 2,
            managerBWins: 1,
            ties: 0,
            averageScore: 128.4,
            biggestWin: "Jordan Lee by 18.5",
            streak: "Jordan Lee W1",
            matchups: [
              {
                season: 2025,
                week: 7,
                winnerKey: "espn-owner:owner-1",
                scoreSummary: "Jordan Lee 138.4 - Riley Morgan 119.9"
              }
            ],
            caveats: ["Playoff split omitted: source matchups do not mark playoff games."]
          }
        ]
      });
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/formula`) {
      await json(route, 200, fixtureProductPayload);
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/data-health`) {
      await json(route, 200, fixtureProductPayload);
      return;
    }

    if (pathname === `/v1/admin/import-runs`) {
      await json(route, 200, {
        runs: [
          {
            runId: testRunId,
            leagueId: testLeagueUuid,
            status: "queued",
            step: "fetch_core",
            credentialVersion: 1,
            warnings: [],
            createdAt: "2026-06-25T15:00:00Z"
          }
        ]
      });
      return;
    }

    if (pathname === `/v1/leagues/${testLeagueUuid}/share-links`) {
      if (request.method() === "POST") {
        await json(route, 200, shareLink(false));
        return;
      }
      await json(route, 200, { shareLinks: [shareLink(false)] });
      return;
    }

    if (pathname === `/v1/share-links/${testShareLinkId}`) {
      await json(route, 200, shareLink(true));
      return;
    }

    if (pathname === `/v1/share/${testShareSlug}`) {
      await json(route, 200, {
        shareSlug: testShareSlug,
        title: "Privacy-safe MyGM report card",
        privacy:
          "public share excludes raw artifacts, private emails, credentials, and import logs",
        productLabel: "Retrospective GM Rating",
        compositeScore: 87.4,
        managerName: "Jordan Lee",
        teamName: "Waiver Cartographers",
        confidence: "fixture",
        formulaVersion: "current",
        bestMove: "Acquired late-season starter before playoff run",
        caveats: ["2026 excluded from career ratings"]
      });
      return;
    }

    await json(route, 404, { detail: "unhandled product mock route" });
  });
}

export async function installAlphaSession(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem(
      "mygm.alpha.session",
      JSON.stringify({
        userId: "local-alpha-user",
        email: "alpha@example.com",
        alphaAccepted: true,
        inviteCode: "alpha-test",
        internalAdmin: true
      })
    );
  });
}

function productFixturePayload() {
  return {
    dashboard: {
      title: "Retrospective GM Rating",
      formula_version: "mygm-retrospective-v1",
      career_seasons_excluded: [2026],
      data_health_status: "caveated",
      top_manager: {
        score: 79.4449,
        confidence: "low"
      }
    },
    trades: {
      canonical_graded_trade_events: 51,
      ungraded_executed_accepts: 25,
      visible_summary: "51 canonical graded trade events"
    },
    waivers: {
      faab_context: "FAAB context unavailable: bidAmount is always 0",
      type_counts: {
        WAIVER: 2662,
        FREEAGENT: 1237
      }
    },
    formula: {
      version: "mygm-retrospective-v1",
      provenance: "fixture-derived ESPN export analytics",
      name: "Retrospective GM Rating",
      components: {
        consistency: true,
        luck_adjusted_performance: true,
        trade_outcome: true,
        waiver_efficiency: true
      }
    },
    data_health: {
      career_exclusion: "2026 excluded from career ratings",
      status: "caveated",
      warnings: ["25 ungraded executed accepts visible"],
      confidence_caveats: [
        "FAAB context unavailable: bidAmount is always 0",
        "2026 excluded from career ratings"
      ]
    }
  };
}

function historyPayload() {
  return {
    span: "2025–2026",
    seasonCount: 2,
    seasons: [
      {
        season: 2026,
        isPartial: true,
        finalWeek: 3,
        transactionCount: 12,
        champion: null,
        runnerUp: null,
        headline: "In progress through week 3",
        superlatives: []
      },
      {
        season: 2025,
        isPartial: false,
        finalWeek: 14,
        transactionCount: 41,
        champion: {
          managerKey: "espn-owner:owner-1",
          displayName: "Jordan Lee",
          teamName: "Waiver Cartographers"
        },
        runnerUp: { managerKey: testManagerId, displayName: "Riley Morgan" },
        headline: "Jordan Lee won the championship with Waiver Cartographers",
        superlatives: [
          {
            label: "Draft steal",
            displayName: "Jordan Lee",
            detail: "Tank Dell drafted #142, finished #28",
            value: 99.0
          }
        ]
      }
    ],
    champions: [{ managerKey: "espn-owner:owner-1", displayName: "Jordan Lee", titles: 1 }]
  };
}

function playerLeaderboardsPayload() {
  return {
    topWeeks: [
      {
        playerName: "Jahmyr Gibbs",
        position: "RB",
        season: 2025,
        week: 12,
        points: 58.4,
        managerKey: "espn-owner:owner-1",
        displayName: "Jordan Lee",
        teamName: "Buck Hunters"
      },
      {
        playerName: "Tyreek Hill",
        position: "WR",
        season: 2020,
        week: 12,
        points: 57.9,
        managerKey: "espn-owner:owner-2",
        displayName: "Riley Morgan",
        teamName: "The Kill"
      }
    ],
    topSeasons: [
      {
        playerName: "Aaron Rodgers",
        position: "QB",
        season: 2020,
        points: 445.3,
        weeks: 15,
        managerKey: "espn-owner:owner-1",
        displayName: "Jordan Lee",
        teamName: "Buck Hunters"
      }
    ],
    lineupEfficiency: [
      {
        season: 2021,
        managerKey: "espn-owner:owner-2",
        displayName: "Riley Morgan",
        teamName: "The Kill",
        aggregateEfficiency: 93.4,
        avgEfficiency: 92.1,
        benchPoints: 210.5,
        startedPoints: 1820.4,
        optimalPoints: 1949.0,
        weeksCounted: 16
      }
    ]
  };
}

function rivalriesPayload() {
  return {
    managers: [
      { managerKey: "espn-owner:owner-1", displayName: "Jordan Lee" },
      { managerKey: "espn-owner:owner-2", displayName: "Riley Morgan" }
    ],
    edges: [
      {
        managerKey: "espn-owner:owner-1",
        opponentKey: "espn-owner:owner-2",
        opponentDisplayName: "Riley Morgan",
        games: 8,
        wins: 6,
        losses: 2,
        ties: 0,
        winPct: 75.0
      },
      {
        managerKey: "espn-owner:owner-2",
        opponentKey: "espn-owner:owner-1",
        opponentDisplayName: "Jordan Lee",
        games: 8,
        wins: 2,
        losses: 6,
        ties: 0,
        winPct: 25.0
      }
    ],
    summaries: [
      {
        managerKey: "espn-owner:owner-1",
        displayName: "Jordan Lee",
        favorite: { opponentDisplayName: "Riley Morgan", wins: 6, losses: 2, winPct: 75.0 },
        nemesis: { opponentDisplayName: "Casey Morgan", wins: 3, losses: 7, winPct: 30.0 }
      },
      {
        managerKey: "espn-owner:owner-2",
        displayName: "Riley Morgan",
        favorite: { opponentDisplayName: "Alex Rivera", wins: 5, losses: 1, winPct: 83.3 },
        nemesis: { opponentDisplayName: "Jordan Lee", wins: 2, losses: 6, winPct: 25.0 }
      }
    ]
  };
}

function seasonHubPayload() {
  return {
    season: 2025,
    isPartial: false,
    finalWeek: 14,
    transactionCount: 120,
    playoffTeamCount: 6,
    champion: {
      managerKey: "espn-owner:owner-1",
      displayName: "Jordan Lee",
      teamName: "Waiver Cartographers"
    },
    runnerUp: { managerKey: "espn-owner:owner-2", displayName: "Riley Morgan" },
    finalStandings: [
      {
        managerKey: "espn-owner:owner-1",
        displayName: "Jordan Lee",
        teamName: "Waiver Cartographers",
        rankFinal: 1,
        wins: 11,
        losses: 3,
        pointsFor: 1820.4,
        madePlayoffs: true,
        isChampion: true
      },
      {
        managerKey: "espn-owner:owner-2",
        displayName: "Riley Morgan",
        teamName: "Caveat Crew",
        rankFinal: 2,
        wins: 9,
        losses: 5,
        pointsFor: 1705.1,
        madePlayoffs: true,
        isChampion: false
      }
    ],
    draftRecap: {
      pickCount: 150,
      bestSteal: {
        displayName: "Jordan Lee",
        playerName: "Tank Dell",
        overallPick: 142,
        pointsRank: 28
      },
      biggestBust: {
        displayName: "Riley Morgan",
        playerName: "Bust McGee",
        overallPick: 4,
        pointsRank: 88
      }
    },
    superlatives: [{ label: "Draft steal", displayName: "Jordan Lee" }],
    ratings: [
      {
        rank: 1,
        managerKey: "espn-owner:owner-1",
        managerName: "Jordan Lee",
        score: 88.0,
        confidence: "high"
      }
    ],
    review: [
      "Jordan Lee won the championship with Waiver Cartographers (11-3).",
      "Riley Morgan finished runner-up.",
      "120 roster moves logged across the season."
    ]
  };
}

function managerDirectoryPayload() {
  return {
    managers: [
      {
        managerKey: "espn-owner:owner-1",
        displayName: "Jordan Lee",
        latestTeamName: "Waiver Cartographers",
        seasonsPlayed: 5,
        titles: 2,
        winPct: 61.5,
        bestFinish: 1,
        careerRating: 84.0
      },
      {
        managerKey: testManagerId,
        displayName: "Riley Morgan",
        latestTeamName: "Caveat Crew",
        seasonsPlayed: 4,
        titles: 0,
        winPct: 42.0,
        bestFinish: 4,
        careerRating: 58.2
      }
    ]
  };
}

function managerHubPayload() {
  return {
    managerKey: "espn-owner:owner-1",
    displayName: "Jordan Lee",
    teamAliases: [{ season: 2025, teamId: 1, teamName: "Waiver Cartographers" }],
    scoreEligible: true,
    caveats: [],
    careerRating: 84.0,
    ratingComponents: {
      tradeValue: { label: "Trade value", value: 80.0 },
      waiverValue: { label: "Waiver/FA value", value: 90.0 },
      lineupEfficiency: { label: "Lineup efficiency", value: 70.0 },
      recordAndPoints: { label: "Record & points", value: 85.0 }
    },
    career: {
      seasonsPlayed: 5,
      wins: 40,
      losses: 30,
      ties: 0,
      winPct: 57.1,
      titles: 2,
      runnerUps: 1,
      playoffAppearances: 4,
      bestFinish: 1,
      bestFinishSeason: 2024,
      worstFinish: 7,
      avgRating: 78.0,
      seasonLines: [
        {
          season: 2024,
          teamName: "Waiver Cartographers",
          wins: 11,
          losses: 3,
          rankFinal: 1,
          isChampion: true,
          ratingScore: 88.0
        },
        {
          season: 2023,
          teamName: "Waiver Cartographers",
          wins: 8,
          losses: 6,
          rankFinal: 4,
          isChampion: false,
          ratingScore: 71.0
        }
      ],
      eras: [
        {
          kind: "dynasty",
          startSeason: 2023,
          endSeason: 2024,
          titles: 2,
          summary: "Top-3 finishes 2023-2024, 2 titles"
        }
      ]
    },
    value: {
      trade: {
        netPoints: 120.0,
        tradeCount: 8,
        bestTrade: { summary: "2024: acquired Jahmyr Gibbs", netPoints: 88.0, season: 2024 },
        worstTrade: { summary: "2023: dealt away CMC", netPoints: -40.0, season: 2023 },
        partners: [
          { displayName: "Riley Morgan", managerKey: testManagerId, netPoints: 60.0, tradeCount: 3 }
        ]
      },
      waiver: {
        netPoints: 300.0,
        eligibleMoves: 120,
        bestPickup: { summary: "2024: added Tank Dell", points: 76.6, season: 2024 },
        worstDrop: { summary: "2023: dropped Sam LaPorta", points: 120.0, season: 2023 }
      }
    },
    rivalry: {
      favorite: { opponentDisplayName: "Riley Morgan", winPct: 75.0, wins: 6, losses: 2, games: 8 },
      nemesis: { opponentDisplayName: "Casey Morgan", winPct: 30.0, wins: 3, losses: 7, games: 10 },
      edges: []
    }
  };
}

function snapshotProductPayload() {
  return {
    meta: {
      snapshotVersion: "espn-league-analytics-snapshot-v1",
      source: "espn",
      generatedAt: "2026-06-26T12:00:00Z",
      productLabel: "Retrospective GM Rating",
      formulaVersion: "mygm-retrospective-v1",
      importStatus: "published"
    },
    league: {
      leagueId: testLeagueUuid,
      name: "Snapshot Test League",
      platform: "espn"
    },
    seasons: [
      { season: 2025, finalWeek: 14, isPartial: false },
      { season: 2026, finalWeek: 3, isPartial: true }
    ],
    managers: [
      {
        managerKey: "espn-owner:owner-1",
        displayName: "Jordan Lee",
        scoreEligible: true,
        caveats: [],
        teamAliases: [{ season: 2025, teamId: 1, teamName: "Waiver Cartographers" }],
        components: {
          tradePerformance: {
            label: "Trade performance",
            score: 91.2,
            weight: 0.35,
            caveats: []
          },
          waiverPerformance: {
            label: "Waiver performance",
            score: 84.7,
            weight: 0.35,
            caveats: []
          }
        }
      },
      {
        managerKey: testManagerId,
        displayName: "Riley Morgan",
        scoreEligible: false,
        caveats: ["Trade component withheld: no gradable trades"],
        teamAliases: [{ season: 2025, teamId: 2, teamName: "Caveat Crew" }],
        components: {
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
        }
      }
    ],
    leaderboards: {
      allTime: [
        {
          rank: 1,
          managerKey: "espn-owner:owner-1",
          displayName: "Jordan Lee",
          teamName: "Waiver Cartographers",
          score: 88.1,
          confidence: "high",
          scoreEligible: true,
          caveats: [],
          componentBreakdown: {
            tradePerformance: {
              label: "Trade performance",
              score: 91.2,
              weight: 0.35,
              caveats: []
            },
            waiverPerformance: {
              label: "Waiver performance",
              score: 84.7,
              weight: 0.35,
              caveats: []
            }
          }
        },
        {
          rank: 2,
          managerKey: testManagerId,
          displayName: "Riley Morgan",
          teamName: "Caveat Crew",
          score: 0,
          confidence: "caveated",
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
          managerKeys: ["espn-owner:owner-1", testManagerId],
          scoreEligible: true,
          caveats: [],
          netPoints: 14.5
        }
      ]
    },
    waivers: {
      items: [
        {
          moveId: "move-1",
          season: 2025,
          managerKey: "espn-owner:owner-1",
          transactionType: "WAIVER",
          scoreEligible: true,
          caveats: ["FAAB context unavailable"]
        },
        {
          moveId: "move-2",
          season: 2025,
          managerKey: testManagerId,
          transactionType: "FREEAGENT",
          scoreEligible: true,
          caveats: []
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
          managerBKey: testManagerId,
          matchups: [],
          caveats: ["No playoff split available"]
        }
      ]
    },
    dataHealth: {
      status: "caveated",
      caveats: ["FAAB context unavailable", "Trade component withheld: no gradable trades"],
      warnings: ["2026 partial season excluded"],
      withheldScores: ["Trade component for Riley Morgan"],
      careerExcludedSeasons: [2026]
    },
    formula: {
      formulaVersion: "mygm-retrospective-v1",
      provenance: "published ESPN analytics snapshot",
      weights: {
        tradePerformance: 0.35,
        waiverPerformance: 0.35,
        recordAndPoints: 0.2,
        luckAdjusted: 0.1
      }
    }
  };
}

function tradeRows() {
  return [
    {
      tradeId: testTradeId,
      label: "Week 7 value swing",
      season: 2025,
      week: 7,
      date: "2025-10-21",
      managers: [
        {
          managerKey: "espn-owner:alpha",
          displayName: "Jordan Lee",
          teamName: "Waiver Cartographers"
        },
        { managerKey: "espn-owner:bravo", displayName: "Casey Morgan", teamName: "Pocket Passers" }
      ],
      managerKeys: ["espn-owner:alpha", "espn-owner:bravo"],
      sides: [
        {
          managerKey: "espn-owner:alpha",
          managerName: "Jordan Lee",
          teamName: "Waiver Cartographers",
          grade: "A+",
          netPoints: 31.4,
          isObjectiveWinner: true,
          receivedAssets: [
            { name: "Deebo Samuel", postTradePoints: 88.0 },
            { name: "Jahmyr Gibbs", postTradePoints: 120.4 }
          ]
        },
        {
          managerKey: "espn-owner:bravo",
          managerName: "Casey Morgan",
          teamName: "Pocket Passers",
          grade: "C",
          netPoints: -31.4,
          isObjectiveWinner: false,
          receivedAssets: [{ name: "Najee Harris", postTradePoints: 70.1 }]
        }
      ],
      assets: ["Deebo Samuel", "Jahmyr Gibbs", "2026 keeper swap"],
      postTradePoints: 144.8,
      netPoints: 31.4,
      objectiveWinner: "espn-owner:alpha",
      scoreEligible: true,
      sourceRows: [{ sourceId: "txn-trade-001", action: "TRADED" }],
      caveats: []
    },
    {
      tradeId: testCaveatedTradeId,
      label: "Unresolved bench exchange",
      season: 2025,
      week: 8,
      date: "2025-10-28",
      managers: [
        {
          managerKey: "espn-owner:alpha",
          displayName: "Jordan Lee",
          teamName: "Waiver Cartographers"
        },
        { managerKey: "espn-owner:charlie", displayName: "Riley Chen", teamName: "Bye Week Bureau" }
      ],
      managerKeys: ["espn-owner:alpha", "espn-owner:charlie"],
      sides: [
        {
          managerKey: "espn-owner:alpha",
          managerName: "Jordan Lee",
          teamName: "Waiver Cartographers",
          grade: "—",
          isObjectiveWinner: false,
          receivedAssets: [{ name: "Unresolved Player 441" }]
        },
        {
          managerKey: "espn-owner:charlie",
          managerName: "Riley Chen",
          teamName: "Bye Week Bureau",
          grade: "—",
          isObjectiveWinner: false,
          receivedAssets: [{ name: "Depth WR" }]
        }
      ],
      assets: ["Unresolved Player 441", "Depth WR"],
      netPoints: null,
      scoreEligible: false,
      sourceRows: [{ sourceId: "txn-trade-002", action: "TRADED" }],
      caveats: [
        "Missing player point rows; trade remains visible but excluded from score contribution."
      ],
      ungradedReason: "Unresolved player points"
    },
    {
      tradeId: "trade-2024-02",
      label: "2024 playoff push",
      season: 2024,
      week: 11,
      date: "2024-11-12",
      managers: [
        { managerKey: "espn-owner:bravo", displayName: "Casey Morgan", teamName: "Pocket Passers" },
        { managerKey: "espn-owner:delta", displayName: "Alex Rivera", teamName: "Red Zone Audit" }
      ],
      managerKeys: ["espn-owner:bravo", "espn-owner:delta"],
      sides: [
        {
          managerKey: "espn-owner:bravo",
          managerName: "Casey Morgan",
          teamName: "Pocket Passers",
          grade: "B",
          netPoints: 12.1,
          isObjectiveWinner: true,
          receivedAssets: [{ name: "Mike Evans", postTradePoints: 96.3 }]
        },
        {
          managerKey: "espn-owner:delta",
          managerName: "Alex Rivera",
          teamName: "Red Zone Audit",
          grade: "B-",
          netPoints: -12.1,
          isObjectiveWinner: false,
          receivedAssets: [{ name: "RB depth", postTradePoints: 41.7 }]
        }
      ],
      assets: ["Mike Evans", "RB depth"],
      postTradePoints: 88.2,
      netPoints: 12.1,
      scoreEligible: true,
      sourceRows: [{ sourceId: "txn-trade-003", action: "TRADED" }],
      caveats: []
    }
  ];
}

function waiverRows() {
  return [
    {
      moveId: testWaiverId,
      label: "Added playoff starter",
      season: 2025,
      week: 9,
      date: "2025-11-04",
      managerKey: "espn-owner:alpha",
      managerName: "Jordan Lee",
      teamName: "Waiver Cartographers",
      transactionType: "WAIVER",
      addedPlayers: ["Tank Dell"],
      droppedPlayers: ["Bench Defense"],
      addedRestOfSeasonPoints: 76.6,
      droppedRestOfSeasonPoints: 8.4,
      dropRegret: -8.4,
      netPoints: 68.2,
      scoreEligible: true,
      sourceRows: [{ sourceId: "txn-waiver-001", action: "ADD" }],
      caveats: ["FAAB context unavailable: bidAmount is always 0"]
    },
    {
      moveId: testCaveatedWaiverId,
      label: "Dropped unresolved player",
      season: 2025,
      week: 10,
      date: "2025-11-11",
      managerKey: "espn-owner:alpha",
      managerName: "Jordan Lee",
      teamName: "Waiver Cartographers",
      transactionType: "FREEAGENT",
      addedPlayers: ["Streaming TE"],
      droppedPlayers: ["Unresolved Player 882"],
      netPoints: null,
      scoreEligible: false,
      sourceRows: [{ sourceId: "txn-waiver-002", action: "DROP" }],
      caveats: ["Missing add/drop point rows; move is excluded from waiver score."],
      exclusionReason: "No resolved rest-of-season points"
    },
    {
      moveId: "move-2024-02",
      label: "Regretful drop",
      season: 2024,
      week: 12,
      date: "2024-11-19",
      managerKey: "espn-owner:bravo",
      managerName: "Casey Morgan",
      teamName: "Pocket Passers",
      transactionType: "WAIVER",
      addedPlayers: ["Backup RB"],
      droppedPlayers: ["Breakout WR"],
      addedRestOfSeasonPoints: 12.2,
      droppedRestOfSeasonPoints: 92.3,
      dropRegret: 92.3,
      netPoints: -80.1,
      scoreEligible: true,
      sourceRows: [{ sourceId: "txn-waiver-003", action: "DROP" }],
      caveats: []
    }
  ];
}

function shareLink(revoked: boolean) {
  return {
    shareLinkId: testShareLinkId,
    shareSlug: testShareSlug,
    leagueId: testLeagueUuid,
    versionId: testVersionId,
    revoked
  };
}

function reprocessRun() {
  return {
    runId: testReprocessRunId,
    leagueId: testLeagueUuid,
    status: "queued",
    step: "derive_snapshot",
    sourceCounts: {
      managers: 2,
      trades: 3,
      waivers: 3
    },
    caveats: ["2026 excluded from career ratings"],
    warnings: [],
    errorSummary: null,
    createdAt: "2026-06-26T12:05:00Z"
  };
}

async function json(route: Route, status: number, body: unknown) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body)
  });
}
