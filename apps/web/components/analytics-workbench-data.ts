import type { InsightMetric, InsightTone } from "@/components/product-insights";
import type { AnalyticsData, DashboardData } from "@/lib/product-api";
import { scoreLine } from "@/lib/product-model";
import { formatNumber } from "./product-insights";

export type AnalyticsKind = "season" | "gms" | "trades" | "waivers" | "records";

type MetricInput = {
  readonly label: string;
  readonly value: string;
  readonly detail: string;
  readonly tone: InsightTone;
};

export function summaryMetrics(
  kind: AnalyticsKind,
  analytics: AnalyticsData,
  row: DashboardData | undefined
): readonly InsightMetric[] {
  const counts = row?.counts;
  const source = row?.sourceCounts;
  switch (kind) {
    case "trades":
      return [
        metric({
          label: "Executed accepts",
          value: formatNumber(source?.executedAcceptedTrades),
          detail: "Accepted trades found in the ESPN export.",
          tone: "info"
        }),
        metric({
          label: "Graded trade rows",
          value: formatNumber(source?.gradedTradeRows),
          detail: "Rows with enough inputs for outcome grading.",
          tone: "success"
        }),
        metric({
          label: "Canonical events",
          value: formatNumber(counts?.canonicalTradeEvents),
          detail: "Grouped trade events shown in the product contract.",
          tone: "success"
        }),
        metric({
          label: "Withheld accepts",
          value: formatNumber(counts?.ungradedExecutedAccepts),
          detail: "Visible but not graded when inputs are incomplete.",
          tone: "warning"
        })
      ];
    case "waivers":
      return [
        metric({
          label: "Waiver rows",
          value: formatNumber(counts?.waiverRows),
          detail: "Priority waiver acquisitions available for review.",
          tone: "success"
        }),
        metric({
          label: "Free-agent rows",
          value: formatNumber(counts?.freeAgentRows),
          detail: "Open-market acquisitions retained beside waiver moves.",
          tone: "info"
        }),
        metric({
          label: "FAAB context",
          value: "Withheld",
          detail: "bidAmount is always 0 in this ESPN export.",
          tone: "warning"
        }),
        metric({
          label: "Surface score",
          value: scoreLine(row?.compositeScore),
          detail: analytics.confidence,
          tone: "neutral"
        })
      ];
    case "records":
      return [
        metric({
          label: "Box score payloads",
          value: formatNumber(source?.boxScorePayloads),
          detail: "Matchup payloads available for records.",
          tone: "info"
        }),
        metric({
          label: "Career seasons",
          value: formatNumber(source?.careerSeasonsIncluded),
          detail: "Completed seasons included in career context.",
          tone: "success"
        }),
        metric({
          label: "Current score",
          value: scoreLine(row?.compositeScore),
          detail: "Records surface summary.",
          tone: "neutral"
        }),
        metric({
          label: "Coverage",
          value: analytics.sourceCoverage,
          detail: analytics.modelVersion,
          tone: "neutral"
        })
      ];
    case "gms":
      return [
        metric({
          label: "Leaderboard score",
          value: scoreLine(row?.compositeScore),
          detail: "Current all-time GM rating surface.",
          tone: "success"
        }),
        metric({
          label: "Player-week rows",
          value: formatNumber(source?.playerWeekRows),
          detail: "Scoring rows behind retrospective value.",
          tone: "info"
        }),
        metric({
          label: "Confidence",
          value: analytics.confidence,
          detail: "Shown beside every ranking.",
          tone: "neutral"
        }),
        metric({
          label: "Formula alias",
          value: analytics.modelVersion,
          detail: analytics.sourceCoverage,
          tone: "neutral"
        })
      ];
    case "season":
      return [
        metric({
          label: "Season score",
          value: scoreLine(row?.compositeScore),
          detail: "Selected season rating surface.",
          tone: "success"
        }),
        metric({
          label: "Player-week rows",
          value: formatNumber(source?.playerWeekRows),
          detail: "Rows available for player value context.",
          tone: "info"
        }),
        metric({
          label: "Transaction payloads",
          value: formatNumber(source?.transactionPeriodPayloads),
          detail: "Transaction periods retained for the season.",
          tone: "neutral"
        }),
        metric({
          label: "Confidence",
          value: analytics.confidence,
          detail: analytics.sourceCoverage,
          tone: "neutral"
        })
      ];
    default:
      return assertNever(kind);
  }
}

function metric(input: MetricInput): InsightMetric {
  return input;
}

function assertNever(value: never): never {
  throw new Error(`Unhandled analytics kind: ${value}`);
}
