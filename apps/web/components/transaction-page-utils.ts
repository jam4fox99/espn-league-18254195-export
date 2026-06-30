"use client";

import type { SnapshotDetailData, SnapshotRowsData } from "@/lib/product-api";

export type SnapshotRow = SnapshotRowsData["rows"][number];

export type SelectOption = {
  readonly value: string;
  readonly label: string;
};

export type DetailState =
  | { readonly kind: "idle" }
  | { readonly kind: "loading" }
  | { readonly kind: "loaded"; readonly item: SnapshotDetailData["item"] }
  | { readonly kind: "error"; readonly message: string };

export function stringField(row: SnapshotRow, key: string): string | undefined {
  const value = row[key];
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

export function numberField(row: SnapshotRow, key: string): number | undefined {
  const value = row[key];
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

export function booleanField(row: SnapshotRow, key: string): boolean | undefined {
  const value = row[key];
  return typeof value === "boolean" ? value : undefined;
}

export function stringArrayField(row: SnapshotRow, key: string): readonly string[] {
  const value = row[key];
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

export function objectArrayField(row: SnapshotRow, key: string): readonly SnapshotRow[] {
  const value = row[key];
  return Array.isArray(value)
    ? value.filter((item): item is SnapshotRow => isSnapshotRow(item))
    : [];
}

export function formatNumber(value: number | undefined): string {
  return value === undefined
    ? "Unresolved"
    : value.toLocaleString("en-US", { maximumFractionDigits: 1 });
}

export function formatSigned(value: number | undefined): string {
  if (value === undefined) {
    return "Unresolved";
  }
  const formatted = Math.abs(value).toLocaleString("en-US", { maximumFractionDigits: 1 });
  return value > 0 ? `+${formatted}` : value < 0 ? `-${formatted}` : "0";
}

export function formatDate(row: SnapshotRow): string {
  return stringField(row, "date") ?? stringField(row, "transactionDate") ?? "Date unavailable";
}

export function rowTitle(row: SnapshotRow, fallback: string): string {
  return (
    stringField(row, "label") ??
    stringField(row, "summary") ??
    stringField(row, "title") ??
    fallback
  );
}

export function rowCaveats(row: SnapshotRow): readonly string[] {
  return uniqueStrings([
    ...stringArrayField(row, "caveats"),
    ...stringArrayField(row, "scoreCaveats"),
    stringField(row, "exclusionReason"),
    stringField(row, "ungradedReason")
  ]);
}

export function eligibilityText(row: SnapshotRow): string {
  const eligible = booleanField(row, "scoreEligible");
  if (eligible === true) {
    return "Score eligible";
  }
  if (eligible === false) {
    return "Excluded from score";
  }
  return "Eligibility unresolved";
}

export function detailRows(row: SnapshotRow): readonly SnapshotRow[] {
  const explicitRows = objectArrayField(row, "sourceRows");
  if (explicitRows.length > 0) {
    return explicitRows;
  }
  const sourceIds = stringArrayField(row, "sourceTransactionIds");
  return sourceIds.map((sourceId) => ({ sourceId }));
}

export function managerOptions(rows: readonly SnapshotRow[]): readonly SelectOption[] {
  const options = new Map<string, string>();
  for (const row of rows) {
    for (const manager of managersForRow(row)) {
      options.set(manager.value, manager.label);
    }
  }
  return [...options.entries()]
    .map(([value, label]) => ({ value, label }))
    .sort((left, right) => left.label.localeCompare(right.label));
}

export function seasonOptions(rows: readonly SnapshotRow[]): readonly string[] {
  return [...new Set(rows.map((row) => numberField(row, "season")).filter(isNumber))]
    .sort((left, right) => right - left)
    .map(String);
}

export function managersForRow(row: SnapshotRow): readonly SelectOption[] {
  const keyedManagers = objectArrayField(row, "managers").map((manager) => {
    const value = stringField(manager, "managerKey") ?? stringField(manager, "key");
    return {
      value,
      label:
        stringField(manager, "displayName") ??
        stringField(manager, "managerName") ??
        stringField(manager, "teamName") ??
        value
    };
  });
  const fromObjects = keyedManagers.filter(
    (manager): manager is SelectOption => manager.value !== undefined && manager.label !== undefined
  );
  if (fromObjects.length > 0) {
    return fromObjects;
  }

  const keys = stringArrayField(row, "managerKeys");
  if (keys.length > 0) {
    const names = stringArrayField(row, "managerNames");
    return keys.map((key, index) => ({
      value: key,
      label: names[index] ?? humanizeManagerKey(key)
    }));
  }

  const managerKey = stringField(row, "managerKey");
  if (managerKey !== undefined) {
    return [
      {
        value: managerKey,
        label:
          stringField(row, "managerName") ??
          stringField(row, "teamName") ??
          humanizeManagerKey(managerKey)
      }
    ];
  }

  return [];
}

// Machine manager keys (espn-owner:{…}, unresolved:2020:0) must never reach the UI.
// Resolved names arrive on the row from the API; this is the readable last resort.
export function humanizeManagerKey(key: string | undefined): string {
  if (key === undefined || key.length === 0) {
    return "Unknown manager";
  }
  return key.startsWith("unresolved") ? "Unresolved manager" : "League manager";
}

export function playersText(row: SnapshotRow, keys: readonly string[]): string {
  for (const key of keys) {
    const players = stringArrayField(row, key);
    if (players.length > 0) {
      return players.join(", ");
    }
    const objects = objectArrayField(row, key)
      .map(
        (item) =>
          stringField(item, "name") ?? stringField(item, "playerName") ?? stringField(item, "label")
      )
      .filter((value): value is string => value !== undefined);
    if (objects.length > 0) {
      return objects.join(", ");
    }
  }
  return "Source rows unresolved";
}

export type TradeAsset = {
  readonly name: string;
  readonly points: number | undefined;
  readonly weekly: readonly number[];
  readonly playerId?: number | undefined;
  readonly proTeamAbbrev?: string | undefined;
  readonly isDST?: boolean | undefined;
  readonly position?: string | undefined;
  readonly badge?: string | undefined;
};

// Pull the 2K player-chip identity fields (headshot id + team/pos) off an asset
// object when the source carries them; absent fields fall back to a name-only chip.
function assetIdentity(asset: SnapshotRow): {
  readonly playerId?: number | undefined;
  readonly proTeamAbbrev?: string | undefined;
  readonly isDST?: boolean | undefined;
  readonly position?: string | undefined;
  readonly badge?: string | undefined;
} {
  return {
    playerId: numberField(asset, "playerId"),
    proTeamAbbrev: stringField(asset, "proTeamAbbrev"),
    isDST: booleanField(asset, "isDST"),
    position: stringField(asset, "position"),
    badge: stringField(asset, "badge")
  };
}

export type TradeSide = {
  readonly managerKey: string | undefined;
  readonly managerName: string;
  readonly teamName: string | undefined;
  readonly grade: string | undefined;
  readonly netPoints: number | undefined;
  readonly isWinner: boolean;
  readonly assets: readonly TradeAsset[];
};

// Parse the snapshot trade `sides` into structured, player-level data for the
// trade analyzer. Empty for unresolved 2020 trades whose source had no items.
export function tradeSides(row: SnapshotRow): readonly TradeSide[] {
  return objectArrayField(row, "sides").map((side) => ({
    managerKey: stringField(side, "managerKey"),
    managerName:
      stringField(side, "managerName") ??
      stringField(side, "displayName") ??
      humanizeManagerKey(stringField(side, "managerKey")),
    teamName: stringField(side, "teamName"),
    grade: stringField(side, "grade"),
    netPoints: numberField(side, "netPoints"),
    isWinner: booleanField(side, "isObjectiveWinner") === true,
    assets: objectArrayField(side, "receivedAssets").map((asset) => ({
      name: stringField(asset, "name") ?? stringField(asset, "playerName") ?? "Unknown player",
      points: numberField(asset, "postTradePoints") ?? numberField(asset, "restOfSeasonPoints"),
      weekly: weeklyPointsOf(asset),
      ...assetIdentity(asset)
    }))
  }));
}

export function hasTradeSides(row: SnapshotRow): boolean {
  return objectArrayField(row, "sides").length > 0;
}

function weeklyPointsOf(asset: SnapshotRow): readonly number[] {
  const weekly = asset["weeklyPoints"];
  if (typeof weekly !== "object" || weekly === null || Array.isArray(weekly)) {
    return [];
  }
  return Object.entries(weekly as Record<string, unknown>)
    .map(([week, points]) => [Number(week), typeof points === "number" ? points : 0] as const)
    .filter(([week]) => Number.isFinite(week))
    .sort((left, right) => left[0] - right[0])
    .map(([, points]) => points);
}

// Player add/drop objects for a waiver/free-agent row.
export function playerObjects(row: SnapshotRow, keys: readonly string[]): readonly TradeAsset[] {
  for (const key of keys) {
    const objects = objectArrayField(row, key);
    if (objects.length > 0) {
      return objects.map((item) => ({
        name: stringField(item, "name") ?? stringField(item, "playerName") ?? "Unknown player",
        points: numberField(item, "restOfSeasonPoints") ?? numberField(item, "postTradePoints"),
        weekly: weeklyPointsOf(item),
        ...assetIdentity(item)
      }));
    }
    const names = stringArrayField(row, key);
    if (names.length > 0) {
      return names.map((name) => ({ name, points: undefined, weekly: [] }));
    }
  }
  return [];
}

export function sortByNumericField(
  rows: readonly SnapshotRow[],
  field: string,
  direction: "asc" | "desc"
): readonly SnapshotRow[] {
  return [...rows].sort((left, right) => {
    const leftValue = numberField(left, field) ?? Number.NEGATIVE_INFINITY;
    const rightValue = numberField(right, field) ?? Number.NEGATIVE_INFINITY;
    return direction === "desc" ? rightValue - leftValue : leftValue - rightValue;
  });
}

function isSnapshotRow(value: unknown): value is SnapshotRow {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNumber(value: number | undefined): value is number {
  return value !== undefined;
}

function uniqueStrings(values: readonly (string | undefined)[]): readonly string[] {
  return [
    ...new Set(values.filter((value): value is string => value !== undefined && value.length > 0))
  ];
}
