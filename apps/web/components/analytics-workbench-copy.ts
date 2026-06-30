import type { AnalyticsKind } from "@/components/analytics-workbench-data";

export type AsideCopy = {
  readonly title: string;
  readonly lines: readonly string[];
};

export function asideCopyFor(kind: AnalyticsKind, sourceCoverage: string): AsideCopy {
  switch (kind) {
    case "trades":
      return {
        title: "How to read trade grades",
        lines: [
          "Grades are retrospective value captured, not advice.",
          "Withheld accepts stay visible when grading inputs are incomplete.",
          sourceCoverage
        ]
      };
    case "waivers":
      return {
        title: "Waiver context",
        lines: [
          "FAAB context unavailable: bidAmount is always 0",
          "Waiver and free-agent acquisitions are separated.",
          sourceCoverage
        ]
      };
    case "records":
      return {
        title: "Records boundary",
        lines: [
          "Partial 2026 data is not included in career ratings.",
          "Records use matchup and career-season coverage.",
          sourceCoverage
        ]
      };
    case "season":
      return {
        title: "Season boundary",
        lines: [
          "Season pages are scoped snapshots.",
          "Career ratings apply separate exclusion rules.",
          sourceCoverage
        ]
      };
    case "gms":
      return {
        title: "Manager report card",
        lines: [
          "Open the report-card route to inspect a privacy-safe manager summary.",
          "The leaderboard is source-covered and retrospective.",
          sourceCoverage
        ]
      };
    default:
      return assertNever(kind);
  }
}

export function workspaceTitle(kind: AnalyticsKind): string {
  switch (kind) {
    case "trades":
      return "Trade review workspace";
    case "waivers":
      return "Waiver acquisition workspace";
    case "records":
      return "Records workspace";
    case "gms":
      return "GM rating workspace";
    case "season":
      return "Season review workspace";
    default:
      return assertNever(kind);
  }
}

export function introFor(kind: AnalyticsKind): string {
  switch (kind) {
    case "trades":
      return "Trade outcomes are grouped into graded events and withheld accepts so the alpha shows what it can and cannot score.";
    case "waivers":
      return "Acquisition context is split between waiver moves and free-agent pickups, with FAAB caveats kept visible.";
    case "records":
      return "Records stay tied to matchup payloads and completed career seasons instead of presenting uncaveated all-time claims.";
    case "gms":
      return "The leaderboard is the entry point for report cards and source-covered retrospective scoring.";
    case "season":
      return "Season surfaces summarize one year of value-captured context before career aggregation.";
    default:
      return assertNever(kind);
  }
}

function assertNever(value: never): never {
  throw new Error(`Unhandled analytics kind: ${value}`);
}
