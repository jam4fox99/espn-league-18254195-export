export const fixtureIds = {
  managerId: "33333333-3333-4333-8333-333333333333",
  versionId: "44444444-4444-4444-8444-444444444444",
  shareLinkId: "55555555-5555-4555-8555-555555555555"
} as const;

export type ProductRouteKind =
  | "dashboard"
  | "season"
  | "gms"
  | "manager"
  | "trades"
  | "waivers"
  | "records"
  | "formula"
  | "data-health";

export function productTitle(kind: ProductRouteKind): string {
  switch (kind) {
    case "dashboard":
      return "League dashboard";
    case "season":
      return "Season overview";
    case "gms":
      return "GM leaderboard";
    case "manager":
      return "Manager report card";
    case "trades":
      return "Trade grades";
    case "waivers":
      return "Waiver grades";
    case "records":
      return "All-time records";
    case "formula":
      return "Formula and provenance";
    case "data-health":
      return "Data health";
    default:
      return assertNever(kind);
  }
}

function assertNever(value: never): never {
  throw new Error(`Unhandled product route kind: ${value}`);
}
