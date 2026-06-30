import type {
  AnalyticsData,
  DashboardData,
  DataHealthData,
  FormulaData,
  ManagerReportData,
  PublicShareData
} from "@/lib/product-api";

export type ProductFacts = {
  readonly ratingLabel: string;
  readonly canonicalGradedTradeEvents: number | null;
  readonly ungradedExecutedAccepts: number | null;
  readonly faabContext: string | null;
  readonly careerExcludedSeasons: readonly number[];
  readonly caveats: readonly string[];
};

export function factsFromDashboard(dashboard: DashboardData): ProductFacts {
  return {
    ratingLabel: dashboard.productLabel ?? dashboard.ratingLabel ?? "Retrospective GM Rating",
    canonicalGradedTradeEvents:
      dashboard.counts?.canonicalTradeEvents ?? dashboard.canonicalGradedTradeEvents ?? null,
    ungradedExecutedAccepts:
      dashboard.counts?.ungradedExecutedAccepts ?? dashboard.ungradedExecutedAccepts ?? null,
    faabContext: dashboard.faabContext ?? null,
    careerExcludedSeasons: dashboard.careerExcludedSeasons ?? [],
    caveats: dashboard.caveats ?? []
  };
}

export function factsFromDataHealth(dataHealth: DataHealthData): ProductFacts {
  return {
    ratingLabel: "Retrospective GM Rating",
    canonicalGradedTradeEvents: null,
    ungradedExecutedAccepts: dataHealth.ungradedExecutedAccepts ?? null,
    faabContext: dataHealth.faabContext ?? null,
    careerExcludedSeasons: dataHealth.careerExcludedSeasons ?? [],
    caveats: dataHealth.caveats ?? (dataHealth.caveat ? [dataHealth.caveat] : dataHealth.warnings)
  };
}

export function productFactStatus(facts: ProductFacts): "ready" | "pending-api-fields" {
  return facts.canonicalGradedTradeEvents === null ||
    facts.ungradedExecutedAccepts === null ||
    facts.faabContext === null ||
    !facts.careerExcludedSeasons.includes(2026)
    ? "pending-api-fields"
    : "ready";
}

export function scoreLine(value: number | null | undefined): string {
  return typeof value === "number" ? `${value.toFixed(1)} / 100` : "Unavailable";
}

export function analyticsScore(analytics: AnalyticsData): number {
  return analytics.rows[0]?.compositeScore ?? 0;
}

export function formulaVersion(formula: FormulaData): string {
  return formula.formulaVersion ?? formula.caveat;
}

export function publicShareTitle(share: PublicShareData): string {
  return share.managerName && share.teamName
    ? `${share.managerName} · ${share.teamName}`
    : share.title;
}

export function managerTitle(report: ManagerReportData): string {
  return report.managerName && report.teamName
    ? `${report.managerName} · ${report.teamName}`
    : (report.managerName ??
        report.displayName ??
        `Manager ${report.managerKey ?? report.managerId}`);
}
