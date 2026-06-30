import type { AnalyticsKind } from "@/components/analytics-workbench-data";
import type { DashboardData } from "@/lib/product-api";
import { scoreLine } from "@/lib/product-model";
import { formatNumber } from "./product-insights";

export type DetailRow = {
  readonly label: string;
  readonly value: string;
  readonly detail: string;
};

export function detailRowsFor(
  kind: AnalyticsKind,
  row: DashboardData | undefined,
  sourceCoverage: string
): readonly DetailRow[] {
  const counts = row?.counts;
  const source = row?.sourceCounts;
  switch (kind) {
    case "trades":
      return [
        detail(
          "Canonical graded trade events",
          formatNumber(counts?.canonicalTradeEvents),
          "Events grouped for the public trade-grade surface."
        ),
        detail(
          "Ungraded executed accepts",
          formatNumber(counts?.ungradedExecutedAccepts),
          "Executed accepts withheld instead of given false precision."
        ),
        detail(
          "Executed accepted trades",
          formatNumber(source?.executedAcceptedTrades),
          "Total accepted trade rows found in ESPN activity."
        ),
        detail(
          "Trade-grade rows",
          formatNumber(source?.gradedTradeRows),
          "Rows with enough post-trade value data for grading."
        )
      ];
    case "waivers":
      return [
        detail(
          "Waiver rows",
          formatNumber(counts?.waiverRows),
          "Rows where the transaction type is WAIVER."
        ),
        detail(
          "Free-agent rows",
          formatNumber(counts?.freeAgentRows),
          "Rows where the transaction type is FREEAGENT."
        ),
        detail(
          "FAAB caveat",
          row?.faabContext ?? "FAAB context unavailable: bidAmount is always 0",
          "Auction bid context is shown as unavailable, not inferred."
        ),
        detail("Source coverage", sourceCoverage, "Why this surface is safe to show in the alpha.")
      ];
    case "records":
      return [
        detail(
          "Box score payloads",
          formatNumber(source?.boxScorePayloads),
          "Matchups available for records and scoring context."
        ),
        detail(
          "Career seasons included",
          formatNumber(source?.careerSeasonsIncluded),
          "Completed seasons used for career records."
        ),
        detail(
          "Current score",
          scoreLine(row?.compositeScore),
          "Records surface score for this alpha version."
        ),
        detail("Caveat", row?.caveats?.[0] ?? sourceCoverage, "Current provenance note.")
      ];
    case "gms":
      return [
        detail(
          "Leaderboard basis",
          scoreLine(row?.compositeScore),
          "All-time retrospective GM rating, not a projection."
        ),
        detail(
          "Confidence",
          row?.importStatus ?? "available",
          "The ranking is visible with import/source status."
        ),
        detail("Source coverage", sourceCoverage, "Where this leaderboard data came from."),
        detail(
          "Report card",
          "Open manager report card",
          "Inspect the privacy-safe manager page linked below."
        )
      ];
    case "season":
      return [
        detail(
          "Season rating",
          scoreLine(row?.compositeScore),
          "Selected season retrospective surface."
        ),
        detail(
          "Player-week rows",
          formatNumber(source?.playerWeekRows),
          "Weekly player values backing the surface."
        ),
        detail(
          "Transaction periods",
          formatNumber(source?.transactionPeriodPayloads),
          "Transaction-period payloads retained for the season."
        ),
        detail("Source coverage", sourceCoverage, "Current alpha provenance.")
      ];
    default:
      return assertNever(kind);
  }
}

function detail(label: string, value: string, detailText: string): DetailRow {
  return { label, value, detail: detailText };
}

function assertNever(value: never): never {
  throw new Error(`Unhandled analytics kind: ${value}`);
}
