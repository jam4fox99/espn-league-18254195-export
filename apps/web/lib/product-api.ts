import ky, { HTTPError } from "ky";
import { z } from "zod";
import { readPublicEnv } from "@/lib/env";
import type { AlphaSession } from "@/lib/session";
import { createAlphaBearer } from "@/lib/session";

const uuidSchema = z.string().uuid();
const scoreSchema = z.number();
const retrospectiveLabel = "Retrospective GM Rating";
const snapshotSourceCoverage = "Published ESPN analytics snapshot";
const formulaProvenance = "fixture-derived ESPN export analytics";
const faabContext = "FAAB context unavailable: bidAmount is always 0";
const careerExclusion = "2026 excluded from career ratings";

const sourceCountsSchema = z
  .object({
    seasons: z.number().int().nonnegative().optional(),
    playerWeekRows: z.number().int().nonnegative().optional(),
    waiverRows: z.number().int().nonnegative().optional(),
    freeAgentRows: z.number().int().nonnegative().optional(),
    executedAcceptedTrades: z.number().int().nonnegative().optional(),
    gradedTradeRows: z.number().int().nonnegative().optional(),
    canonicalTradeEvents: z.number().int().nonnegative().optional(),
    ungradedExecutedAccepts: z.number().int().nonnegative().optional(),
    boxScorePayloads: z.number().int().nonnegative().optional(),
    transactionPeriodPayloads: z.number().int().nonnegative().optional(),
    zipEntries: z.number().int().nonnegative().optional(),
    nonDirectoryFiles: z.number().int().nonnegative().optional(),
    careerSeasonsIncluded: z.number().int().nonnegative().optional()
  })
  .catchall(z.number().int().nonnegative());

const snapshotManagerKeySchema = z.string().min(1);

const scoreComponentSchema = z
  .object({
    label: z.string().optional(),
    score: scoreSchema.nullable().optional(),
    value: scoreSchema.nullable().optional(),
    weight: z.number().optional(),
    scoreEligible: z.boolean().optional(),
    caveats: z.array(z.string()).optional()
  })
  .passthrough();

const componentBreakdownSchema = z.record(z.string(), scoreComponentSchema);

// --- 2K UI additions: per-manager logo, signature player, player dimension ---
const signaturePlayerSchema = z
  .object({
    name: z.string(),
    playerId: z.number().int(),
    season: z.number().int().optional(),
    points: z.number().optional(),
    headshot: z.string().optional()
  })
  .passthrough();

const managerLogoSchema = z
  .object({
    main: z.string().nullable().optional(),
    mainSeason: z.number().int().nullable().optional(),
    bySeason: z.record(z.string(), z.string()).default({})
  })
  .passthrough();

// Manager archetype ("GM DNA") — one career best-fit label + one-line description.
const archetypeSchema = z
  .object({
    name: z.string(),
    oneLiner: z.string().optional(),
    runnerUp: z.string().optional(),
    scores: z.record(z.string(), z.number()).optional(),
    signals: z.record(z.string(), z.number()).optional()
  })
  .passthrough();

const playerDirectoryEntrySchema = z
  .object({
    playerId: z.number().int(),
    name: z.string(),
    position: z.string().default(""),
    proTeamAbbrev: z.string().default(""),
    latestSeason: z.number().int().optional(),
    isDST: z.boolean().default(false),
    badge: z.string().optional().catch(undefined)
  })
  .passthrough();

const playerDirectorySchema = z.record(z.string(), playerDirectoryEntrySchema);

const teamAliasSchema = z
  .object({
    season: z.number().int().optional(),
    teamId: z.union([z.string(), z.number()]).optional(),
    teamName: z.string().optional()
  })
  .passthrough();

const leaderboardViewRowSchema = z
  .object({
    rank: z.number().int().optional(),
    managerKey: snapshotManagerKeySchema,
    managerName: z.string().optional(),
    displayName: z.string().optional(),
    teamName: z.string().optional(),
    score: scoreSchema.nullable().optional(),
    confidence: z.string().optional(),
    scoreEligible: z.boolean().optional(),
    caveats: z.array(z.string()).optional(),
    componentBreakdown: componentBreakdownSchema.optional(),
    components: componentBreakdownSchema.optional(),
    logo: managerLogoSchema.nullable().optional(),
    signaturePlayer: signaturePlayerSchema.nullable().optional(),
    // The API sends `{}` for managers with no archetype; degrade that to undefined.
    archetype: archetypeSchema.nullable().optional().catch(undefined)
  })
  .passthrough();

const dashboardSchema = z.object({
  leagueId: uuidSchema,
  version: z.string(),
  importStatus: z.string(),
  compositeScore: scoreSchema,
  leagueName: z.string().optional(),
  snapshotVersion: z.string().optional(),
  generatedAt: z.string().optional(),
  formulaVersion: z.string().optional(),
  availableSeasons: z.array(z.number().int()).optional(),
  leaderboard: z.array(leaderboardViewRowSchema).optional(),
  productLabel: z.string().optional(),
  ratingLabel: z.string().optional(),
  canonicalGradedTradeEvents: z.number().int().nonnegative().optional(),
  ungradedExecutedAccepts: z.number().int().nonnegative().optional(),
  faabContext: z.string().optional(),
  careerExcludedSeasons: z.array(z.number().int()).optional(),
  caveats: z.array(z.string()).optional(),
  counts: z
    .object({
      canonicalTradeEvents: z.number().int().nonnegative().optional(),
      ungradedExecutedAccepts: z.number().int().nonnegative().optional(),
      waiverRows: z.number().int().nonnegative().optional(),
      freeAgentRows: z.number().int().nonnegative().optional()
    })
    .optional(),
  sourceCounts: sourceCountsSchema.optional()
});

const analyticsSchema = z.object({
  modelName: z.string(),
  modelVersion: z.string(),
  confidence: z.string(),
  sourceCoverage: z.string(),
  rows: z.array(dashboardSchema)
});

const snapshotJsonObjectSchema = z.record(z.string(), z.unknown());

const waiverSuperlativeCardSchema = z
  .object({
    managerKey: z.string(),
    displayName: z.string(),
    value: z.number().optional(),
    player: z.string().default(""),
    count: z.number().optional(),
    season: z.number().optional(),
    week: z.number().optional(),
    netVor: z.number().optional(),
    detail: z.string().default("")
  })
  .passthrough();

const waiverSuperlativeSeasonSchema = z
  .object({
    season: z.number(),
    bestPickup: waiverSuperlativeCardSchema.nullable().optional().catch(undefined),
    worstDrop: waiverSuperlativeCardSchema.nullable().optional().catch(undefined),
    bestWireValue: waiverSuperlativeCardSchema.nullable().optional().catch(undefined),
    mostActive: waiverSuperlativeCardSchema.nullable().optional().catch(undefined)
  })
  .passthrough();

const snapshotRowsSchema = z.object({
  modelName: z.string(),
  modelVersion: z.string(),
  rows: z.array(snapshotJsonObjectSchema),
  // Waivers carry per-season award cards; other rows endpoints send {}.
  waiverSuperlatives: z.record(z.string(), waiverSuperlativeSeasonSchema).default({})
});

const snapshotDetailSchema = z.object({
  item: snapshotJsonObjectSchema
});

const apiAnalyticsRowSchema = z
  .object({
    label: z.string().optional(),
    value: scoreSchema.nullable().optional(),
    counts: sourceCountsSchema.optional(),
    rank: z.number().int().optional(),
    managerKey: snapshotManagerKeySchema.optional(),
    managerName: z.string().optional(),
    displayName: z.string().optional(),
    teamName: z.string().optional(),
    score: scoreSchema.nullable().optional(),
    confidence: z.string().optional(),
    scoreEligible: z.boolean().optional(),
    caveats: z.array(z.string()).optional(),
    componentBreakdown: componentBreakdownSchema.optional(),
    components: componentBreakdownSchema.optional()
  })
  .passthrough();

const apiAnalyticsSchema = z.object({
  modelName: z.string(),
  modelVersion: z.string(),
  confidence: z.string(),
  sourceCoverage: z.string(),
  rows: z.array(apiAnalyticsRowSchema)
});

// The snapshot rows endpoints (gms, season) return {modelName, modelVersion, rows}
// without the top-level confidence/sourceCoverage that apiAnalyticsSchema requires.
const snapshotAnalyticsSchema = z.object({
  modelName: z.string(),
  modelVersion: z.string(),
  rows: z.array(apiAnalyticsRowSchema)
});

const managerMoveSchema = z
  .object({
    label: z.string().optional(),
    detail: z.string().optional(),
    value: scoreSchema.nullable().optional(),
    season: z.number().int().optional(),
    caveats: z.array(z.string()).optional()
  })
  .passthrough();

const managerReportSchema = z
  .object({
    managerId: z.string().optional(),
    managerKey: snapshotManagerKeySchema.optional(),
    version: z.string().optional(),
    compositeScore: scoreSchema.nullable().optional(),
    score: scoreSchema.nullable().optional(),
    confidence: z.string().optional(),
    managerName: z.string().optional(),
    displayName: z.string().optional(),
    teamName: z.string().optional(),
    teamAliases: z.array(teamAliasSchema).optional(),
    scoreEligible: z.boolean().optional(),
    caveats: z.array(z.string()).optional(),
    componentBreakdown: componentBreakdownSchema.optional(),
    components: componentBreakdownSchema.optional(),
    allTimeStats: z
      .record(z.string(), z.union([z.string(), z.number(), z.boolean(), z.null()]))
      .optional(),
    seasonStats: z
      .array(z.record(z.string(), z.union([z.string(), z.number(), z.boolean(), z.null()])))
      .optional(),
    bestMove: z.string().optional(),
    worstMove: z.string().optional(),
    bestMoves: z.array(managerMoveSchema).optional(),
    worstMoves: z.array(managerMoveSchema).optional(),
    archetype: archetypeSchema.nullable().optional().catch(undefined)
  })
  .passthrough()
  .transform((report) => ({
    ...report,
    managerId: report.managerId ?? report.managerKey ?? "unknown-manager",
    managerKey: report.managerKey ?? report.managerId ?? "unknown-manager",
    version: report.version ?? "current",
    compositeScore: report.compositeScore ?? report.score ?? null,
    confidence: report.confidence ?? "caveated",
    managerName: report.managerName ?? report.displayName,
    componentBreakdown: report.componentBreakdown ?? report.components ?? {}
  }));

const formulaSummarySchema = z
  .object({
    formulaVersion: z.string().optional(),
    label: z.string().optional(),
    weights: z.record(z.string(), z.number()).catch({}),
    componentLabels: z.record(z.string(), z.string()).catch({}),
    deprecated: z.boolean().catch(false),
    caveat: z.string().optional()
  })
  .passthrough();

const formulaSchema = z.object({
  scoreModels: z.array(z.string()),
  caveat: z.string(),
  provenance: z.string().optional(),
  formulaVersion: z.string().optional(),
  label: z.string().optional(),
  weights: z.record(z.string(), z.number()).catch({}),
  componentLabels: z.record(z.string(), z.string()).catch({}),
  availableFormulas: z.array(formulaSummarySchema).catch([])
});

const newsItemSchema = z
  .object({
    id: z.string(),
    type: z.string(),
    headline: z.string(),
    detail: z.string(),
    season: z.number(),
    managerKey: z.string().optional(),
    managerKeys: z.array(z.string()).optional(),
    displayName: z.string().optional(),
    veto: z.object({ percent: z.number(), band: z.string() }).nullish(),
    grades: z.record(z.string(), z.string()).optional(),
    contenders: z
      .array(
        z
          .object({
            week: z.number().optional(),
            displayName: z.string().optional(),
            points: z.number().optional()
          })
          .passthrough()
      )
      .optional()
  })
  .passthrough();

const teamStrengthSchema = z
  .object({
    managerKey: z.string(),
    displayName: z.string(),
    weakestPosition: z.string().nullish(),
    strongestPosition: z.string().optional(),
    needs: z.record(z.string(), z.number()).catch({})
  })
  .passthrough();

const waiverSuggestionSchema = z
  .object({
    managerKey: z.string(),
    displayName: z.string(),
    weakPositions: z.array(z.string()).catch([]),
    suggestions: z
      .array(
        z
          .object({
            position: z.string(),
            playerId: z.number().optional(),
            name: z.string(),
            trailingPoints: z.number()
          })
          .passthrough()
      )
      .catch([])
  })
  .passthrough();

const leagueNewsSchema = z.object({
  season: z.number(),
  items: z.array(newsItemSchema).catch([]),
  teamStrength: z.array(teamStrengthSchema).catch([]),
  waiverSuggestions: z.array(waiverSuggestionSchema).catch([])
});

const dataHealthSchema = z.object({
  modelName: z.string(),
  warnings: z.array(z.string()),
  withheldScores: z.array(z.string()),
  caveat: z.string().optional(),
  caveats: z.array(z.string()).optional(),
  ungradedExecutedAccepts: z.number().int().nonnegative().optional(),
  faabContext: z.string().optional(),
  careerExcludedSeasons: z.array(z.number().int()).optional()
});

const snapshotMetaSchema = z.object({
  snapshotVersion: z.literal("espn-league-analytics-snapshot-v1"),
  source: z.literal("espn"),
  generatedAt: z.string(),
  productLabel: z.string(),
  formulaVersion: z.string(),
  importStatus: z.string()
});

const snapshotManagerSchema = z
  .object({
    managerKey: snapshotManagerKeySchema,
    displayName: z.string(),
    scoreEligible: z.boolean(),
    caveats: z.array(z.string()),
    teamAliases: z.array(teamAliasSchema).optional(),
    components: componentBreakdownSchema.optional(),
    componentBreakdown: componentBreakdownSchema.optional()
  })
  .passthrough();

const snapshotLeaderboardRowSchema = leaderboardViewRowSchema.extend({
  rank: z.number().int(),
  score: scoreSchema.nullable(),
  confidence: z.string()
});

const snapshotTradeSchema = z
  .object({
    tradeId: z.string().min(1),
    season: z.number().int(),
    managerKeys: z.array(snapshotManagerKeySchema).min(2),
    scoreEligible: z.boolean(),
    caveats: z.array(z.string())
  })
  .passthrough();

const snapshotWaiverSchema = z
  .object({
    moveId: z.string().min(1),
    season: z.number().int(),
    managerKey: snapshotManagerKeySchema,
    transactionType: z.string(),
    scoreEligible: z.boolean(),
    caveats: z.array(z.string())
  })
  .passthrough();

const snapshotRecordSchema = z
  .object({
    recordId: z.string().min(1),
    category: z.string(),
    label: z.string(),
    value: scoreSchema,
    managerKey: snapshotManagerKeySchema.optional()
  })
  .passthrough();

const snapshotHeadToHeadPairSchema = z
  .object({
    pairId: z.string().min(1),
    managerAKey: snapshotManagerKeySchema,
    managerBKey: snapshotManagerKeySchema,
    matchups: z.array(z.record(z.string(), z.string().or(z.number()).or(z.boolean()))),
    caveats: z.array(z.string())
  })
  .passthrough();

export const leagueAnalyticsSnapshotSchema = z.object({
  meta: snapshotMetaSchema,
  league: z.object({
    leagueId: z.string().min(1),
    name: z.string(),
    platform: z.literal("espn")
  }),
  seasons: z.array(
    z.object({
      season: z.number().int(),
      finalWeek: z.number().int().nonnegative(),
      isPartial: z.boolean()
    })
  ),
  managers: z.array(snapshotManagerSchema).min(1),
  leaderboards: z.object({
    allTime: z.array(snapshotLeaderboardRowSchema),
    bySeason: z.array(snapshotLeaderboardRowSchema)
  }),
  trades: z.object({ items: z.array(snapshotTradeSchema) }),
  waivers: z.object({ items: z.array(snapshotWaiverSchema) }),
  records: z.object({ items: z.array(snapshotRecordSchema) }),
  headToHead: z.object({ pairs: z.array(snapshotHeadToHeadPairSchema) }),
  dataHealth: z.object({
    status: z.string(),
    caveats: z.array(z.string()),
    warnings: z.array(z.string()),
    withheldScores: z.array(z.string()),
    careerExcludedSeasons: z.array(z.number().int()).optional()
  }),
  formula: z.object({
    formulaVersion: z.string(),
    provenance: z.string(),
    weights: z.record(z.string(), z.number())
  })
});

const fixtureDashboardSchema = z.object({
  title: z.string(),
  formula_version: z.string(),
  career_seasons_excluded: z.array(z.number().int()).default([]),
  data_health_status: z.string().optional(),
  top_manager: z
    .object({
      score: scoreSchema,
      confidence: z.string().optional()
    })
    .optional()
});

const fixtureTradesSchema = z.object({
  canonical_graded_trade_events: z.number().int().nonnegative(),
  ungraded_executed_accepts: z.number().int().nonnegative(),
  visible_summary: z.string().optional()
});

const fixtureWaiversSchema = z.object({
  faab_context: z.string(),
  type_counts: z
    .object({
      WAIVER: z.number().int().nonnegative().optional(),
      FREEAGENT: z.number().int().nonnegative().optional()
    })
    .optional()
});

const fixtureFormulaSchema = z.object({
  version: z.string(),
  provenance: z.string(),
  name: z.string().optional(),
  components: z.record(z.string(), z.unknown()).optional()
});

const fixtureDataHealthSchema = z.object({
  career_exclusion: z.string(),
  status: z.string(),
  warnings: z.array(z.string()).default([]),
  confidence_caveats: z.array(z.string()).default([])
});

const fixturePayloadSchema = z.object({
  dashboard: fixtureDashboardSchema,
  trades: fixtureTradesSchema.optional(),
  waivers: fixtureWaiversSchema.optional(),
  formula: fixtureFormulaSchema.optional(),
  data_health: fixtureDataHealthSchema.optional()
});

const importRunsSchema = z.object({
  runs: z.array(
    z.object({
      runId: uuidSchema,
      leagueId: uuidSchema,
      status: z.string(),
      step: z.string(),
      credentialVersion: z.number().int().positive(),
      warnings: z.array(z.string()),
      createdAt: z.string()
    })
  )
});

const reprocessRunSchema = z.object({
  runId: uuidSchema,
  leagueId: uuidSchema,
  status: z.string(),
  step: z.string(),
  sourceCounts: sourceCountsSchema,
  caveats: z.array(z.string()),
  warnings: z.array(z.string()),
  errorSummary: z.string().nullable().optional(),
  createdAt: z.string()
});

const shareLinkSchema = z.object({
  shareLinkId: uuidSchema,
  shareSlug: z.string(),
  leagueId: uuidSchema,
  versionId: uuidSchema,
  revoked: z.boolean()
});

const shareListSchema = z.object({
  shareLinks: z.array(shareLinkSchema)
});

const publicShareSchema = z.object({
  shareSlug: z.string(),
  title: z.string(),
  privacy: z.string(),
  compositeScore: scoreSchema,
  productLabel: z.string().optional(),
  managerName: z.string().optional(),
  teamName: z.string().optional(),
  confidence: z.string().optional(),
  ratingLabel: z.string().optional(),
  formulaVersion: z.string().optional(),
  bestMove: z.string().optional(),
  caveats: z.array(z.string()).optional()
});

const historyManagerRefSchema = z
  .object({
    managerKey: z.string().optional(),
    displayName: z.string().optional(),
    teamName: z.string().optional()
  })
  .passthrough();

const historySuperlativeSchema = z
  .object({
    label: z.string().optional(),
    displayName: z.string().optional(),
    detail: z.string().optional(),
    value: scoreSchema.nullable().optional(),
    managerKey: z.string().optional()
  })
  .passthrough();

const historySeasonSchema = z.object({
  season: z.number().int(),
  isPartial: z.boolean(),
  finalWeek: z.number().int().nullable().optional(),
  transactionCount: z.number().int().nullable().optional(),
  champion: historyManagerRefSchema.nullable().optional(),
  runnerUp: historyManagerRefSchema.nullable().optional(),
  headline: z.string(),
  superlatives: z.array(historySuperlativeSchema).default([])
});

const historyChampionSchema = z.object({
  managerKey: z.string(),
  displayName: z.string(),
  titles: z.number().int()
});

const leagueHistorySchema = z.object({
  span: z.string(),
  seasonCount: z.number().int(),
  seasons: z.array(historySeasonSchema),
  champions: z.array(historyChampionSchema)
});

const managerDirectoryEntrySchema = z
  .object({
    managerKey: z.string(),
    displayName: z.string(),
    latestTeamName: z.string().nullable().optional(),
    seasonsPlayed: z.number().nullable().optional(),
    titles: z.number().nullable().optional(),
    winPct: z.number().nullable().optional(),
    bestFinish: z.number().nullable().optional(),
    careerRating: z.number().nullable().optional(),
    logo: managerLogoSchema.nullable().optional(),
    signaturePlayer: signaturePlayerSchema.nullable().optional()
  })
  .passthrough();

const managerDirectorySchema = z.object({
  managers: z.array(managerDirectoryEntrySchema)
});

const seasonLineSchema = z
  .object({
    season: z.number(),
    teamName: z.string().optional(),
    wins: z.number().optional(),
    losses: z.number().optional(),
    ties: z.number().optional(),
    rankFinal: z.number().optional(),
    pointsFor: z.number().optional(),
    madePlayoffs: z.boolean().optional(),
    isChampion: z.boolean().optional(),
    ratingScore: z.number().nullable().optional()
  })
  .passthrough();

const eraSchema = z
  .object({
    kind: z.string(),
    startSeason: z.number(),
    endSeason: z.number(),
    summary: z.string().optional(),
    titles: z.number().optional(),
    seasons: z.array(z.number()).optional()
  })
  .passthrough();

const careerSchema = z
  .object({
    seasonsPlayed: z.number().optional(),
    wins: z.number().optional(),
    losses: z.number().optional(),
    ties: z.number().optional(),
    winPct: z.number().optional(),
    titles: z.number().optional(),
    runnerUps: z.number().optional(),
    playoffAppearances: z.number().optional(),
    bestFinish: z.number().optional(),
    bestFinishSeason: z.number().optional(),
    worstFinish: z.number().optional(),
    avgRating: z.number().optional(),
    pointsFor: z.number().optional(),
    pointsAgainst: z.number().optional(),
    mostPointsSeason: z.number().optional(),
    seasonLines: z.array(seasonLineSchema).default([]),
    eras: z.array(eraSchema).default([])
  })
  .passthrough();

const tradeRefSchema = z
  .object({
    summary: z.string().optional(),
    netPoints: z.number().nullable().optional(),
    season: z.number().optional(),
    tradeId: z.string().optional()
  })
  .passthrough();

const tradePartnerSchema = z
  .object({
    displayName: z.string().optional(),
    managerKey: z.string().optional(),
    netPoints: z.number().optional(),
    tradeCount: z.number().optional()
  })
  .passthrough();

const tradeValueSchema = z
  .object({
    netPoints: z.number().optional(),
    receivedPoints: z.number().optional(),
    sentPoints: z.number().optional(),
    tradeCount: z.number().optional(),
    bestTrade: tradeRefSchema.nullable().optional(),
    worstTrade: tradeRefSchema.nullable().optional(),
    partners: z.array(tradePartnerSchema).default([])
  })
  .passthrough();

const waiverRefSchema = z
  .object({
    summary: z.string().optional(),
    points: z.number().nullable().optional(),
    season: z.number().optional()
  })
  .passthrough();

const waiverValueSchema = z
  .object({
    netPoints: z.number().optional(),
    addedPoints: z.number().optional(),
    droppedPoints: z.number().optional(),
    eligibleMoves: z.number().optional(),
    bestPickup: waiverRefSchema.nullable().optional(),
    worstDrop: waiverRefSchema.nullable().optional()
  })
  .passthrough();

const managerValueSchema = z
  .object({
    trade: tradeValueSchema.optional(),
    waiver: waiverValueSchema.optional()
  })
  .passthrough();

const rivalryEdgeSchema = z
  .object({
    opponentKey: z.string().optional(),
    opponentDisplayName: z.string().optional(),
    games: z.number().optional(),
    wins: z.number().optional(),
    losses: z.number().optional(),
    ties: z.number().optional(),
    winPct: z.number().optional(),
    currentStreak: z.string().optional(),
    averagePointsFor: z.number().optional(),
    averagePointsAgainst: z.number().optional(),
    playoffWins: z.number().optional(),
    playoffLosses: z.number().optional()
  })
  .passthrough();

const rivalrySchema = z
  .object({
    favorite: rivalryEdgeSchema.nullable().optional(),
    nemesis: rivalryEdgeSchema.nullable().optional(),
    edges: z.array(rivalryEdgeSchema).default([])
  })
  .passthrough();

const hubDraftPickSchema = z
  .object({
    playerName: z.string().optional(),
    position: z.string().optional(),
    overallPick: z.number().optional(),
    round: z.number().optional(),
    season: z.number().nullable().optional(),
    surplus: z.number().optional(),
    seasonVor: z.number().optional(),
    pointsRank: z.number().optional()
  })
  .passthrough();

const hubDraftCardSchema = z
  .object({
    bestPick: hubDraftPickSchema.nullish(),
    worstPick: hubDraftPickSchema.nullish(),
    careerSurplus: z.number().optional()
  })
  .passthrough();

const rosterEntrySchema = z
  .object({
    playerId: z.number(),
    name: z.string(),
    position: z.string().default(""),
    slot: z.string().default(""),
    proTeam: z.string().default(""),
    season: z.number().optional(),
    ppg: z.number().optional(),
    gamesStarted: z.number().optional(),
    totalPoints: z.number().optional(),
    started: z.boolean().optional()
  })
  .passthrough();

const rosterCornerstoneSchema = z
  .object({
    playerId: z.number(),
    name: z.string(),
    position: z.string().default(""),
    proTeam: z.string().default(""),
    weeksStarted: z.number(),
    totalPoints: z.number().optional(),
    firstSeason: z.number().optional(),
    lastSeason: z.number().optional(),
    seasonCount: z.number().optional()
  })
  .passthrough();

const rosterBestSeasonSchema = z
  .object({
    season: z.number(),
    metric: z.string().default("pointsFor"),
    pointsFor: z.number().optional(),
    lineup: z.array(rosterEntrySchema).default([])
  })
  .passthrough();

const rosterSeasonRosterSchema = z
  .object({
    season: z.number(),
    groups: z
      .array(
        z
          .object({
            position: z.string(),
            players: z.array(rosterEntrySchema).default([])
          })
          .passthrough()
      )
      .default([])
  })
  .passthrough();

const rosterHistorySchema = z
  .object({
    allTimeLineup: z.array(rosterEntrySchema).default([]),
    allTimeByTotalPoints: z.array(rosterEntrySchema).default([]),
    depthChart: z.record(z.string(), z.array(rosterEntrySchema)).default({}),
    cornerstones: z.array(rosterCornerstoneSchema).default([]),
    bestSeason: rosterBestSeasonSchema.nullable().optional().catch(undefined),
    seasonRosters: z.array(rosterSeasonRosterSchema).default([])
  })
  .passthrough();

const managerHubSchema = z
  .object({
    managerKey: z.string(),
    displayName: z.string(),
    teamAliases: z.array(teamAliasSchema).default([]),
    scoreEligible: z.boolean(),
    caveats: z.array(z.string()).default([]),
    careerRating: z.number().nullable().optional(),
    ratingComponents: z.record(z.string(), scoreComponentSchema).default({}),
    career: careerSchema,
    value: managerValueSchema,
    rivalry: rivalrySchema,
    logo: managerLogoSchema.nullable().optional(),
    signaturePlayer: signaturePlayerSchema.nullable().optional(),
    // The API sends `{}` for managers with no archetype; degrade that to undefined.
    archetype: archetypeSchema.nullable().optional().catch(undefined),
    // `{}` for managers with no resolvable draft (keepers/unresolved) → undefined.
    draftCard: hubDraftCardSchema.optional().catch(undefined),
    // `{}` for managers with no box-score roster history → undefined.
    rosterHistory: rosterHistorySchema.optional().catch(undefined)
  })
  .passthrough();

const standingRowSchema = z
  .object({
    managerKey: z.string().optional(),
    displayName: z.string().optional(),
    teamName: z.string().optional(),
    rankFinal: z.number().optional(),
    playoffSeed: z.number().optional(),
    wins: z.number().optional(),
    losses: z.number().optional(),
    ties: z.number().optional(),
    pointsFor: z.number().optional(),
    pointsAgainst: z.number().optional(),
    madePlayoffs: z.boolean().optional(),
    isChampion: z.boolean().optional()
  })
  .passthrough();

const draftPickRefSchema = z
  .object({
    displayName: z.string().optional(),
    managerKey: z.string().optional(),
    playerName: z.string().optional(),
    overallPick: z.number().optional(),
    pointsRank: z.number().optional(),
    seasonPoints: z.number().optional(),
    stealValue: z.number().optional(),
    round: z.number().optional()
  })
  .passthrough();

const draftRecapSchema = z
  .object({
    bestSteal: draftPickRefSchema.nullable().optional(),
    biggestBust: draftPickRefSchema.nullable().optional(),
    pickCount: z.number().nullable().optional()
  })
  .passthrough();

const seasonHubSchema = z.object({
  season: z.number(),
  isPartial: z.boolean(),
  finalWeek: z.number().nullable().optional(),
  transactionCount: z.number().nullable().optional(),
  playoffTeamCount: z.number().nullable().optional(),
  champion: historyManagerRefSchema.nullable().optional(),
  runnerUp: historyManagerRefSchema.nullable().optional(),
  finalStandings: z.array(standingRowSchema).default([]),
  draftRecap: draftRecapSchema.default({}),
  superlatives: z.array(historySuperlativeSchema).default([]),
  ratings: z.array(apiAnalyticsRowSchema).default([]),
  review: z.array(z.string()).default([])
});

export type SeasonHubData = z.infer<typeof seasonHubSchema>;
export type SeasonStandingRow = z.infer<typeof standingRowSchema>;
const rivalryManagerRefSchema = z
  .object({
    managerKey: z.string(),
    displayName: z.string()
  })
  .passthrough();

const rivalryMatrixEdgeSchema = rivalryEdgeSchema.extend({
  managerKey: z.string().optional()
});

const rivalrySummarySchema = z
  .object({
    managerKey: z.string(),
    displayName: z.string(),
    favorite: rivalryEdgeSchema.nullable().optional(),
    nemesis: rivalryEdgeSchema.nullable().optional()
  })
  .passthrough();

const rivalryMatrixSchema = z.object({
  managers: z.array(rivalryManagerRefSchema).default([]),
  edges: z.array(rivalryMatrixEdgeSchema).default([]),
  summaries: z.array(rivalrySummarySchema).default([])
});

const playerWeekSchema = z
  .object({
    playerName: z.string(),
    position: z.string().default(""),
    season: z.number().int(),
    week: z.number().int(),
    points: z.number(),
    managerKey: z.string().optional(),
    displayName: z.string().default(""),
    teamName: z.string().default(""),
    playerId: z.number().int().nullable().optional(),
    proTeamAbbrev: z.string().optional(),
    isDST: z.boolean().optional(),
    badge: z.string().optional().catch(undefined)
  })
  .passthrough();

const playerSeasonSchema = z
  .object({
    playerName: z.string(),
    position: z.string().default(""),
    season: z.number().int(),
    points: z.number(),
    weeks: z.number().int().default(0),
    managerKey: z.string().optional(),
    displayName: z.string().default(""),
    teamName: z.string().default(""),
    playerId: z.number().int().nullable().optional(),
    proTeamAbbrev: z.string().optional(),
    isDST: z.boolean().optional(),
    badge: z.string().optional().catch(undefined)
  })
  .passthrough();

const lineupEfficiencyRowSchema = z
  .object({
    season: z.number().int(),
    managerKey: z.string().optional(),
    displayName: z.string().default(""),
    teamName: z.string().default(""),
    aggregateEfficiency: z.number().default(0),
    avgEfficiency: z.number().default(0),
    benchPoints: z.number().default(0),
    startedPoints: z.number().default(0),
    optimalPoints: z.number().default(0),
    weeksCounted: z.number().int().default(0)
  })
  .passthrough();

const playerLeaderboardsSchema = z.object({
  topWeeks: z.array(playerWeekSchema).default([]),
  topSeasons: z.array(playerSeasonSchema).default([]),
  lineupEfficiency: z.array(lineupEfficiencyRowSchema).default([]),
  playerDirectory: playerDirectorySchema.default({})
});

const recordBookRowSchema = z
  .object({
    recordId: z.string().optional(),
    category: z.string().default("records"),
    label: z.string(),
    value: z.union([z.string(), z.number()]),
    managerKey: z.string().optional(),
    managerName: z.string().optional(),
    teamName: z.string().optional(),
    season: z.number().int().nullable().optional(),
    detail: z.string().nullable().optional(),
    caveats: z.array(z.string()).optional(),
    playerId: z.number().int().nullable().optional(),
    playerName: z.string().optional(),
    proTeamAbbrev: z.string().optional(),
    isDST: z.boolean().optional(),
    logo: managerLogoSchema.nullable().optional()
  })
  .passthrough();

const recordBookSchema = z.object({
  modelName: z.string().default("records"),
  modelVersion: z.string().default("current"),
  rows: z.array(recordBookRowSchema).default([])
});

export type RivalryMatrixData = z.infer<typeof rivalryMatrixSchema>;
export type RivalryMatrixEdge = z.infer<typeof rivalryMatrixEdgeSchema>;
export type RivalrySummary = z.infer<typeof rivalrySummarySchema>;
export type PlayerLeaderboardsData = z.infer<typeof playerLeaderboardsSchema>;
export type PlayerWeekRow = z.infer<typeof playerWeekSchema>;
export type PlayerSeasonRow = z.infer<typeof playerSeasonSchema>;
export type SignaturePlayer = z.infer<typeof signaturePlayerSchema>;
export type Archetype = z.infer<typeof archetypeSchema>;
export type ManagerLogoData = z.infer<typeof managerLogoSchema>;
export type PlayerDirectory = z.infer<typeof playerDirectorySchema>;
export type PlayerDirectoryEntry = z.infer<typeof playerDirectoryEntrySchema>;
export type LineupEfficiencyRow = z.infer<typeof lineupEfficiencyRowSchema>;
export type RecordBookData = z.infer<typeof recordBookSchema>;
export type RecordBookRow = z.infer<typeof recordBookRowSchema>;
export type ManagerDirectoryData = z.infer<typeof managerDirectorySchema>;
export type ManagerDirectoryEntry = z.infer<typeof managerDirectoryEntrySchema>;
export type ManagerHubData = z.infer<typeof managerHubSchema>;
export type RosterHistoryData = z.infer<typeof rosterHistorySchema>;
export type RosterEntry = z.infer<typeof rosterEntrySchema>;
export type RosterCornerstone = z.infer<typeof rosterCornerstoneSchema>;
export type RosterBestSeason = z.infer<typeof rosterBestSeasonSchema>;
export type RosterSeasonRoster = z.infer<typeof rosterSeasonRosterSchema>;
export type WaiverSuperlativeSeason = z.infer<typeof waiverSuperlativeSeasonSchema>;
export type WaiverSuperlativeCard = z.infer<typeof waiverSuperlativeCardSchema>;
export type DraftCardData = z.infer<typeof hubDraftCardSchema>;
export type DraftPickRef = z.infer<typeof hubDraftPickSchema>;
export type ManagerSeasonLine = z.infer<typeof seasonLineSchema>;
export type ManagerEra = z.infer<typeof eraSchema>;
export type RivalryEdge = z.infer<typeof rivalryEdgeSchema>;
export type LeagueHistoryData = z.infer<typeof leagueHistorySchema>;
export type HistorySeasonData = z.infer<typeof historySeasonSchema>;
export type HistoryChampionData = z.infer<typeof historyChampionSchema>;
export type DashboardData = z.infer<typeof dashboardSchema>;
export type AnalyticsData = z.infer<typeof analyticsSchema>;
export type SnapshotRowsData = z.infer<typeof snapshotRowsSchema>;
export type SnapshotDetailData = z.infer<typeof snapshotDetailSchema>;
export type LeagueAnalyticsSnapshot = z.infer<typeof leagueAnalyticsSnapshotSchema>;
export type ManagerReportData = z.infer<typeof managerReportSchema>;
export type FormulaData = z.infer<typeof formulaSchema>;
export type LeagueNewsData = z.infer<typeof leagueNewsSchema>;
export type LeagueNewsItem = z.infer<typeof newsItemSchema>;
export type TeamStrength = z.infer<typeof teamStrengthSchema>;
export type WaiverSuggestionRow = z.infer<typeof waiverSuggestionSchema>;
export type DataHealthData = z.infer<typeof dataHealthSchema>;
export type ImportRunsData = z.infer<typeof importRunsSchema>;
export type ReprocessRunData = z.infer<typeof reprocessRunSchema>;
export type ShareLinkData = z.infer<typeof shareLinkSchema>;
export type PublicShareData = z.infer<typeof publicShareSchema>;

export class ProductApiError extends Error {
  constructor(
    message: string,
    readonly status: number
  ) {
    super(message);
    this.name = "ProductApiError";
  }
}

export async function readDashboard(
  session: AlphaSession,
  leagueId: string
): Promise<DashboardData> {
  const payload = await protectedJson(session, `v1/leagues/${leagueId}/dashboard`);
  return parseDashboardPayload(payload, leagueId);
}

export async function readHistory(
  session: AlphaSession,
  leagueId: string
): Promise<LeagueHistoryData> {
  return leagueHistorySchema.parse(await protectedJson(session, `v1/leagues/${leagueId}/history`));
}

export async function readRivalries(
  session: AlphaSession,
  leagueId: string
): Promise<RivalryMatrixData> {
  return rivalryMatrixSchema.parse(
    await protectedJson(session, `v1/leagues/${leagueId}/rivalries`)
  );
}

export async function readPlayerLeaderboards(
  session: AlphaSession,
  leagueId: string
): Promise<PlayerLeaderboardsData> {
  return playerLeaderboardsSchema.parse(
    await protectedJson(session, `v1/leagues/${leagueId}/players/leaderboards`)
  );
}

export async function readRecordBook(
  session: AlphaSession,
  leagueId: string
): Promise<RecordBookData> {
  return recordBookSchema.parse(
    await protectedJson(session, `v1/leagues/${leagueId}/records?version=current`)
  );
}

export async function readSeasonHub(
  session: AlphaSession,
  leagueId: string,
  season: string | number
): Promise<SeasonHubData> {
  return seasonHubSchema.parse(
    await protectedJson(session, `v1/leagues/${leagueId}/seasons/${season}/hub`)
  );
}

export async function readManagerDirectory(
  session: AlphaSession,
  leagueId: string
): Promise<ManagerDirectoryData> {
  return managerDirectorySchema.parse(
    await protectedJson(session, `v1/leagues/${leagueId}/managers`)
  );
}

export async function readManagerHub(
  session: AlphaSession,
  leagueId: string,
  managerKey: string
): Promise<ManagerHubData> {
  return managerHubSchema.parse(
    await protectedJson(
      session,
      `v1/leagues/${leagueId}/managers/${encodeURIComponent(managerKey)}`
    )
  );
}

export async function readAnalytics(session: AlphaSession, path: string): Promise<AnalyticsData> {
  const payload = await protectedJson(session, path);
  return parseAnalyticsPayload(payload, path);
}

export async function readSnapshotRows(
  session: AlphaSession,
  path: string
): Promise<SnapshotRowsData> {
  return snapshotRowsSchema.parse(await protectedJson(session, path));
}

export async function readSnapshotDetail(
  session: AlphaSession,
  path: string
): Promise<SnapshotDetailData> {
  return snapshotDetailSchema.parse(await protectedJson(session, path));
}

export async function readManagerReport(
  session: AlphaSession,
  leagueId: string,
  managerId: string
): Promise<ManagerReportData> {
  const payload = await protectedJson(
    session,
    `v1/leagues/${leagueId}/gms/${managerId}?version=current`
  );
  return parseManagerReportPayload(payload, leagueId, managerId);
}

export async function readFormula(session: AlphaSession, leagueId: string): Promise<FormulaData> {
  const payload = await protectedJson(session, `v1/leagues/${leagueId}/formula`);
  return parseFormula(payload);
}

export async function readLeagueNews(
  session: AlphaSession,
  leagueId: string
): Promise<LeagueNewsData> {
  return leagueNewsSchema.parse(await protectedJson(session, `v1/leagues/${leagueId}/news`));
}

export async function readDataHealth(
  session: AlphaSession,
  leagueId: string
): Promise<DataHealthData> {
  const payload = await protectedJson(session, `v1/leagues/${leagueId}/data-health`);
  return parseDataHealth(payload);
}

export async function readAdminImportRuns(session: AlphaSession): Promise<ImportRunsData> {
  return importRunsSchema.parse(await protectedJson(session, "v1/admin/import-runs"));
}

export async function createAnalyticsReprocessRun(
  session: AlphaSession,
  leagueId: string,
  sourceImportRunId: string
): Promise<ReprocessRunData> {
  return reprocessRunSchema.parse(
    await protectedJson(session, `v1/leagues/${leagueId}/reprocess-runs`, {
      method: "post",
      json: {
        sourceImportRunId,
        targets: ["analyticsSnapshot"],
        formulaVersion: "mygm-retrospective-v1"
      }
    })
  );
}

export async function readReprocessRun(
  session: AlphaSession,
  runId: string
): Promise<ReprocessRunData> {
  return reprocessRunSchema.parse(await protectedJson(session, `v1/reprocess-runs/${runId}`));
}

export async function readShareLinks(
  session: AlphaSession,
  leagueId: string
): Promise<readonly ShareLinkData[]> {
  const parsed = shareListSchema.parse(
    await protectedJson(session, `v1/leagues/${leagueId}/share-links`)
  );
  return parsed.shareLinks;
}

export async function createShareLink(
  session: AlphaSession,
  leagueId: string,
  managerId: string,
  versionId: string
): Promise<ShareLinkData> {
  return shareLinkSchema.parse(
    await protectedJson(session, `v1/leagues/${leagueId}/share-links`, {
      method: "post",
      json: {
        managerId,
        versionId,
        expiresAt: null
      }
    })
  );
}

export async function revokeShareLink(
  session: AlphaSession,
  shareLinkId: string
): Promise<ShareLinkData> {
  return shareLinkSchema.parse(
    await protectedJson(session, `v1/share-links/${shareLinkId}`, { method: "delete" })
  );
}

export async function readPublicShare(shareSlug: string): Promise<PublicShareData> {
  return publicShareSchema.parse(await publicJson(`v1/share/${shareSlug}`));
}

export function parseDashboardPayload(payload: unknown, leagueId: string): DashboardData {
  const snapshot = leagueAnalyticsSnapshotSchema.safeParse(payload);
  if (snapshot.success) {
    return dashboardFromSnapshot(snapshot.data, leagueId);
  }

  const parsed = dashboardSchema.safeParse(payload);
  if (parsed.success) {
    return enrichDashboard(parsed.data);
  }

  const fixture = fixturePayloadSchema.parse(payload);
  return dashboardFromFixture(fixture, leagueId);
}

export function parseLeagueAnalyticsSnapshot(
  payload: unknown,
  leagueId: string
): LeagueAnalyticsSnapshot {
  const snapshot = leagueAnalyticsSnapshotSchema.safeParse(payload);
  if (snapshot.success) {
    return snapshot.data;
  }

  return snapshotFromLegacyFixture(fixturePayloadSchema.parse(payload), leagueId);
}

export function parseManagerReportPayload(
  payload: unknown,
  leagueId: string,
  managerId: string
): ManagerReportData {
  const parsed = managerReportSchema.safeParse(payload);
  if (parsed.success) {
    return parsed.data;
  }

  const snapshot = leagueAnalyticsSnapshotSchema.safeParse(payload);
  if (snapshot.success) {
    const manager = snapshot.data.managers.find((item) => item.managerKey === managerId);
    const leaderboardRow = snapshot.data.leaderboards.allTime.find(
      (item) => item.managerKey === managerId
    );
    return managerReportSchema.parse({
      managerId,
      managerKey: managerId,
      version: snapshot.data.meta.formulaVersion,
      compositeScore: leaderboardRow?.score ?? null,
      confidence: leaderboardRow?.confidence ?? "caveated",
      managerName: manager?.displayName ?? managerId,
      teamAliases: manager?.teamAliases ?? [],
      scoreEligible: manager?.scoreEligible ?? false,
      caveats: uniqueStrings([
        ...(manager?.caveats ?? []),
        ...(leaderboardRow?.caveats ?? []),
        ...(snapshot.data.dataHealth.caveats ?? [])
      ]),
      componentBreakdown:
        leaderboardRow?.componentBreakdown ??
        leaderboardRow?.components ??
        manager?.componentBreakdown ??
        manager?.components ??
        {}
    });
  }

  const fixture = fixturePayloadSchema.parse(payload);
  const dashboard = dashboardFromFixture(fixture, leagueId);
  return managerReportSchema.parse({
    managerId,
    managerKey: managerId,
    version: dashboard.version,
    compositeScore: dashboard.compositeScore,
    confidence: fixture.dashboard.top_manager?.confidence ?? "fixture",
    managerName: `Manager ${managerId}`,
    caveats: dashboard.caveats ?? []
  });
}

export function parseAnalyticsPayload(payload: unknown, path: string): AnalyticsData {
  const parsed = analyticsSchema.safeParse(payload);
  if (parsed.success) {
    return { ...parsed.data, rows: parsed.data.rows.map(enrichDashboard) };
  }

  const api = apiAnalyticsSchema.safeParse(payload);
  if (api.success) {
    return analyticsFromApi(api.data, path);
  }

  const snapshotRows = snapshotAnalyticsSchema.safeParse(payload);
  if (snapshotRows.success) {
    const confidence =
      snapshotRows.data.rows.find((row) => typeof row.confidence === "string")?.confidence ??
      "snapshot";
    return analyticsFromApi(
      { ...snapshotRows.data, confidence, sourceCoverage: snapshotSourceCoverage },
      path
    );
  }

  const fixture = fixturePayloadSchema.parse(payload);
  const leagueId = leagueIdFromPath(path);
  const dashboard = dashboardFromFixture(fixture, leagueId);

  if (path.includes("/trades")) {
    return {
      modelName: "trade_outcome_v1",
      modelVersion: fixture.dashboard.formula_version,
      confidence: fixture.dashboard.top_manager?.confidence ?? "fixture",
      sourceCoverage: fixture.formula?.provenance ?? formulaProvenance,
      rows: [dashboard]
    };
  }

  if (path.includes("/waivers")) {
    return {
      modelName: "acquisition_outcome_v1",
      modelVersion: fixture.dashboard.formula_version,
      confidence: fixture.dashboard.top_manager?.confidence ?? "fixture",
      sourceCoverage: fixture.waivers?.faab_context ?? faabContext,
      rows: [dashboard]
    };
  }

  return {
    modelName: path.includes("/records")
      ? "records_v1"
      : path.includes("/gms")
        ? "career_gm_rating_v1"
        : "season_gm_rating_v1",
    modelVersion: fixture.dashboard.formula_version,
    confidence: fixture.dashboard.top_manager?.confidence ?? "fixture",
    sourceCoverage: fixture.formula?.provenance ?? formulaProvenance,
    rows: [dashboard]
  };
}

function parseFormula(payload: unknown): FormulaData {
  const parsed = formulaSchema.safeParse(payload);
  if (parsed.success) {
    return parsed.data;
  }

  // Legacy fixture fallback (raw snapshot formula without the FormulaResponse envelope).
  // The live API path above carries real weights; here we default to empty so the
  // formula page renders its static table rather than fabricating weights.
  const fixture =
    fixturePayloadSchema.safeParse(payload).data?.formula ?? fixtureFormulaSchema.parse(payload);
  return {
    formulaVersion: fixture.version,
    scoreModels: Object.keys(
      fixture.components ?? {
        consistency: true,
        luck_adjusted_performance: true,
        trade_outcome: true,
        waiver_efficiency: true
      }
    ),
    provenance: fixture.provenance,
    caveat: fixture.name ?? retrospectiveLabel,
    weights: {},
    componentLabels: {},
    availableFormulas: []
  };
}

function parseDataHealth(payload: unknown): DataHealthData {
  const parsed = dataHealthSchema.safeParse(payload);
  if (parsed.success) {
    return parsed.data;
  }

  const fixture = fixturePayloadSchema.parse(payload);
  const caveats = uniqueStrings([
    ...(fixture.data_health?.warnings ?? []),
    ...(fixture.data_health?.confidence_caveats ?? [])
  ]);
  const faabContext =
    fixture.waivers?.faab_context ??
    caveats.find((caveat) => caveat.toLowerCase().includes("faab")) ??
    null;
  return {
    modelName: "data_health_v1",
    warnings: caveats,
    withheldScores: faabContext ? ["FAAB-adjusted waiver context"] : [],
    caveats,
    caveat: fixture.data_health?.career_exclusion,
    ungradedExecutedAccepts: fixture.trades?.ungraded_executed_accepts,
    faabContext: faabContext ?? undefined,
    careerExcludedSeasons: fixture.dashboard.career_seasons_excluded
  };
}

function analyticsFromApi(api: z.infer<typeof apiAnalyticsSchema>, path: string): AnalyticsData {
  const leagueId = leagueIdFromPath(path);
  return {
    modelName: api.modelName,
    modelVersion: api.modelVersion,
    confidence: api.confidence,
    sourceCoverage: api.sourceCoverage,
    rows: api.rows.map((row) => {
      const leaderboard = row.managerKey
        ? [
            {
              ...row,
              managerKey: row.managerKey
            }
          ]
        : undefined;
      return enrichDashboard({
        leagueId,
        version: api.modelVersion,
        importStatus: "available",
        compositeScore: row.value ?? row.score ?? 0,
        productLabel: row.label ?? row.displayName ?? row.managerName ?? retrospectiveLabel,
        leaderboard,
        counts: countsFromSourceCounts(row.counts),
        sourceCounts: row.counts,
        caveats: row.caveats
      });
    })
  };
}

function enrichDashboard(dashboard: DashboardData): DashboardData {
  const sourceCounts = dashboard.sourceCounts;
  const counts = countsFromSourceCounts(sourceCounts);
  const canonicalTradeEvents =
    dashboard.counts?.canonicalTradeEvents ??
    dashboard.canonicalGradedTradeEvents ??
    counts?.canonicalTradeEvents;
  const ungradedExecutedAccepts =
    dashboard.counts?.ungradedExecutedAccepts ??
    dashboard.ungradedExecutedAccepts ??
    counts?.ungradedExecutedAccepts;

  return {
    ...dashboard,
    productLabel: dashboard.productLabel ?? dashboard.ratingLabel ?? retrospectiveLabel,
    canonicalGradedTradeEvents: canonicalTradeEvents,
    ungradedExecutedAccepts: ungradedExecutedAccepts,
    faabContext: dashboard.faabContext ?? faabContext,
    careerExcludedSeasons: dashboard.careerExcludedSeasons ?? [2026],
    caveats: uniqueStrings([...(dashboard.caveats ?? []), careerExclusion, faabContext]),
    counts: {
      canonicalTradeEvents,
      ungradedExecutedAccepts,
      waiverRows: dashboard.counts?.waiverRows ?? counts?.waiverRows,
      freeAgentRows: dashboard.counts?.freeAgentRows ?? counts?.freeAgentRows
    }
  };
}

function countsFromSourceCounts(
  sourceCounts: z.infer<typeof sourceCountsSchema> | undefined
): DashboardData["counts"] | undefined {
  if (!sourceCounts) {
    return undefined;
  }

  const ungradedExecutedAccepts =
    sourceCounts.ungradedExecutedAccepts ??
    difference(sourceCounts.executedAcceptedTrades, sourceCounts.gradedTradeRows);

  return {
    canonicalTradeEvents: sourceCounts.canonicalTradeEvents,
    ungradedExecutedAccepts,
    waiverRows: sourceCounts.waiverRows,
    freeAgentRows: sourceCounts.freeAgentRows
  };
}

function difference(left: number | undefined, right: number | undefined): number | undefined {
  return left === undefined || right === undefined ? undefined : Math.max(left - right, 0);
}

function dashboardFromSnapshot(snapshot: LeagueAnalyticsSnapshot, leagueId: string): DashboardData {
  const topManager = snapshot.leaderboards.allTime[0];
  const managerByKey = new Map(snapshot.managers.map((manager) => [manager.managerKey, manager]));
  const leaderboard = snapshot.leaderboards.allTime.map((row) => {
    const manager = managerByKey.get(row.managerKey);
    return {
      ...row,
      managerName: row.managerName ?? row.displayName ?? manager?.displayName,
      displayName: row.displayName ?? row.managerName ?? manager?.displayName,
      teamName: row.teamName ?? manager?.teamAliases?.[0]?.teamName,
      scoreEligible: row.scoreEligible ?? manager?.scoreEligible,
      caveats: uniqueStrings([...(row.caveats ?? []), ...(manager?.caveats ?? [])]),
      componentBreakdown:
        row.componentBreakdown ??
        row.components ??
        manager?.componentBreakdown ??
        manager?.components
    };
  });
  return enrichDashboard({
    leagueId,
    version: snapshot.meta.formulaVersion,
    importStatus: snapshot.meta.importStatus,
    compositeScore: topManager?.score ?? 0,
    leagueName: snapshot.league.name,
    snapshotVersion: snapshot.meta.snapshotVersion,
    generatedAt: snapshot.meta.generatedAt,
    formulaVersion: snapshot.meta.formulaVersion,
    availableSeasons: snapshot.seasons.map((season) => season.season),
    leaderboard,
    productLabel: snapshot.meta.productLabel,
    canonicalGradedTradeEvents: snapshot.trades.items.length,
    faabContext: snapshot.waivers.items[0]?.caveats[0],
    careerExcludedSeasons: snapshot.dataHealth.careerExcludedSeasons,
    caveats: snapshot.dataHealth.caveats,
    counts: {
      canonicalTradeEvents: snapshot.trades.items.length,
      waiverRows: snapshot.waivers.items.length,
      freeAgentRows: snapshot.waivers.items.filter((item) => item.transactionType === "FREEAGENT")
        .length
    }
  });
}

function snapshotFromLegacyFixture(
  fixture: z.infer<typeof fixturePayloadSchema>,
  leagueId: string
): LeagueAnalyticsSnapshot {
  const dashboard = dashboardFromFixture(fixture, leagueId);
  const managerKey = "unresolved:legacy:1";
  return leagueAnalyticsSnapshotSchema.parse({
    meta: {
      snapshotVersion: "espn-league-analytics-snapshot-v1",
      source: "espn",
      generatedAt: "legacy-fixture-adapter",
      productLabel: dashboard.productLabel ?? retrospectiveLabel,
      formulaVersion: dashboard.version,
      importStatus: dashboard.importStatus
    },
    league: { leagueId, name: "Legacy fixture league", platform: "espn" },
    seasons: [
      {
        season: dashboard.careerExcludedSeasons?.[0] ?? 0,
        finalWeek: 0,
        isPartial: true
      }
    ],
    managers: [
      {
        managerKey,
        displayName: managerKey,
        scoreEligible: false,
        caveats: dashboard.caveats ?? []
      }
    ],
    leaderboards: {
      allTime: [
        {
          rank: 1,
          managerKey,
          score: dashboard.compositeScore,
          confidence: "fixture"
        }
      ],
      bySeason: []
    },
    trades: {
      items: [
        {
          tradeId: "legacy-trade-summary",
          season: 0,
          managerKeys: [managerKey, managerKey],
          scoreEligible: false,
          caveats: dashboard.caveats ?? []
        }
      ]
    },
    waivers: {
      items: [
        {
          moveId: "legacy-waiver-summary",
          season: 0,
          managerKey,
          transactionType: "WAIVER",
          scoreEligible: false,
          caveats: [dashboard.faabContext ?? faabContext]
        }
      ]
    },
    records: {
      items: [
        {
          recordId: "legacy-record-summary",
          category: "summary",
          label: "Legacy record summary",
          value: dashboard.compositeScore,
          managerKey
        }
      ]
    },
    headToHead: {
      pairs: [
        {
          pairId: "legacy-pair-summary",
          managerAKey: managerKey,
          managerBKey: managerKey,
          matchups: [],
          caveats: dashboard.caveats ?? []
        }
      ]
    },
    dataHealth: {
      status: "caveated",
      caveats: dashboard.caveats ?? [],
      warnings: dashboard.caveats ?? [],
      withheldScores: dashboard.faabContext ? ["FAAB-adjusted waiver context"] : [],
      careerExcludedSeasons: dashboard.careerExcludedSeasons
    },
    formula: {
      formulaVersion: dashboard.version,
      provenance: fixture.formula?.provenance ?? formulaProvenance,
      weights: {
        tradePerformance: 0.35,
        waiverPerformance: 0.35,
        recordAndPoints: 0.2,
        luckAdjusted: 0.1
      }
    }
  });
}

function dashboardFromFixture(
  fixture: z.infer<typeof fixturePayloadSchema>,
  leagueId: string
): DashboardData {
  return {
    leagueId,
    version: fixture.dashboard.formula_version,
    importStatus: fixture.dashboard.data_health_status ?? "caveated",
    compositeScore: fixture.dashboard.top_manager?.score ?? 0,
    productLabel: fixture.dashboard.title,
    canonicalGradedTradeEvents: fixture.trades?.canonical_graded_trade_events,
    ungradedExecutedAccepts: fixture.trades?.ungraded_executed_accepts,
    faabContext: fixture.waivers?.faab_context,
    careerExcludedSeasons: fixture.dashboard.career_seasons_excluded,
    caveats: fixture.data_health
      ? uniqueStrings([
          fixture.data_health.career_exclusion,
          ...fixture.data_health.confidence_caveats
        ])
      : [],
    counts: {
      canonicalTradeEvents: fixture.trades?.canonical_graded_trade_events,
      ungradedExecutedAccepts: fixture.trades?.ungraded_executed_accepts,
      waiverRows: fixture.waivers?.type_counts?.WAIVER,
      freeAgentRows: fixture.waivers?.type_counts?.FREEAGENT
    }
  };
}

function leagueIdFromPath(path: string): string {
  return path.match(/v1\/leagues\/([^/?]+)/)?.[1] ?? "11111111-1111-4111-8111-111111111111";
}

function uniqueStrings(values: readonly string[]): string[] {
  return [...new Set(values)];
}

async function protectedJson(
  session: AlphaSession,
  path: string,
  options: { readonly method?: "get" | "post" | "delete"; readonly json?: unknown } = {}
): Promise<unknown> {
  return apiJson(path, {
    ...options,
    headers: { Authorization: `Bearer ${createAlphaBearer(session)}` }
  });
}

async function publicJson(path: string): Promise<unknown> {
  return apiJson(path, {});
}

async function apiJson(
  path: string,
  options: {
    readonly method?: "get" | "post" | "delete";
    readonly json?: unknown;
    readonly headers?: Record<string, string>;
  }
): Promise<unknown> {
  const client = ky.create({
    baseUrl: readPublicEnv().NEXT_PUBLIC_API_BASE_URL,
    retry: 0,
    timeout: 10000
  });

  try {
    return await client(path, options).json();
  } catch (error) {
    if (error instanceof HTTPError) {
      throw new ProductApiError(`API request failed for ${path}`, error.response.status);
    }
    throw error;
  }
}
