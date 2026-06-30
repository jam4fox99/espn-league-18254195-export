"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { type Facet, FilterBar, type SortOption, useFacetFilter } from "@/components/controls";
import { LeagueNav, MetricStrip, ProductHeader } from "@/components/product-chrome";
import { ProductLoader } from "@/components/product-loader";
import { StatusPill } from "@/components/status-pill";
import {
  booleanField,
  type DetailState,
  managerOptions,
  managersForRow,
  numberField,
  rowCaveats,
  type SnapshotRow,
  seasonOptions
} from "@/components/transaction-page-utils";
import {
  firstMoveId,
  MoveDetail,
  MoveTable,
  moveId,
  transactionTypeOf,
  transactionTypeOptions,
  WaiverSuperlativeHeader,
  waiverAddDropValues,
  waiverSearchText
} from "@/components/waivers-page-parts";
import { readSnapshotDetail, readSnapshotRows, type SnapshotRowsData } from "@/lib/product-api";
import type { AlphaSession } from "@/lib/session";

const ADD_DROP_OPTIONS = [
  { value: "add", label: "Added" },
  { value: "drop", label: "Dropped" }
];

const WAIVER_SORTS: readonly SortOption<SnapshotRow>[] = [
  {
    value: "newest",
    label: "Newest",
    compare: (left, right) =>
      (numberField(right, "season") ?? 0) - (numberField(left, "season") ?? 0) ||
      (numberField(right, "week") ?? 0) - (numberField(left, "week") ?? 0)
  },
  {
    value: "best-pickup",
    label: "Best pickup",
    compare: (left, right) =>
      (numberField(right, "addedRestOfSeasonPoints") ?? 0) -
      (numberField(left, "addedRestOfSeasonPoints") ?? 0)
  },
  {
    value: "worst-drop",
    label: "Worst drop",
    compare: (left, right) =>
      (numberField(right, "droppedRestOfSeasonPoints") ?? 0) -
      (numberField(left, "droppedRestOfSeasonPoints") ?? 0)
  },
  {
    value: "value",
    label: "Best value (VOR)",
    compare: (left, right) =>
      (numberField(right, "netVor") ?? 0) - (numberField(left, "netVor") ?? 0)
  }
];

export function WaiversPage({ leagueId }: { readonly leagueId: string }) {
  const load = useCallback(
    (session: AlphaSession) =>
      readSnapshotRows(session, `v1/leagues/${leagueId}/waivers?version=current`),
    [leagueId]
  );

  return (
    <ProductLoader load={load}>
      {(data, session) => <WaiversSurface data={data} leagueId={leagueId} session={session} />}
    </ProductLoader>
  );
}

function WaiversSurface({
  data,
  leagueId,
  session
}: {
  readonly data: SnapshotRowsData;
  readonly leagueId: string;
  readonly session: AlphaSession;
}) {
  const facets = useMemo<readonly Facet<SnapshotRow>[]>(
    () => [
      {
        key: "manager",
        label: "Manager",
        options: managerOptions(data.rows),
        valuesOf: (row) => managersForRow(row).map((manager) => manager.value)
      },
      {
        key: "type",
        label: "Type",
        options: transactionTypeOptions(data.rows),
        valuesOf: (row) => [transactionTypeOf(row)]
      },
      {
        key: "addDrop",
        label: "Add / Drop",
        options: ADD_DROP_OPTIONS,
        valuesOf: waiverAddDropValues
      },
      {
        key: "season",
        label: "Season",
        options: seasonOptions(data.rows).map((season) => ({ value: season, label: season })),
        valuesOf: (row) => {
          const season = numberField(row, "season");
          return season === undefined ? [] : [String(season)];
        }
      }
    ],
    [data.rows]
  );

  const filter = useFacetFilter({
    rows: data.rows,
    facets,
    sorts: WAIVER_SORTS,
    searchText: waiverSearchText
  });

  const [selectedId, setSelectedId] = useState(firstMoveId(data.rows));
  const [detail, setDetail] = useState<DetailState>({ kind: "idle" });
  const visibleRows = filter.filtered;
  const selectedRow = visibleRows.find((row) => moveId(row) === selectedId) ?? visibleRows[0];

  const superlativeSeason = useMemo(() => {
    const picked = filter.selected["season"] ?? [];
    if (picked.length === 1 && picked[0]) {
      return picked[0];
    }
    const seasons = Object.keys(data.waiverSuperlatives)
      .map(Number)
      .filter((value) => Number.isFinite(value))
      .sort((a, b) => b - a);
    return seasons[0]?.toString() ?? "";
  }, [filter.selected, data.waiverSuperlatives]);

  useEffect(() => {
    const nextId = selectedRow === undefined ? "" : moveId(selectedRow);
    if (nextId !== selectedId) {
      setSelectedId(nextId);
    }
  }, [selectedId, selectedRow]);

  useEffect(() => {
    if (selectedId.length === 0) {
      setDetail({ kind: "idle" });
      return;
    }
    let active = true;
    setDetail({ kind: "loading" });
    readSnapshotDetail(session, `v1/leagues/${leagueId}/waivers/${selectedId}?version=current`)
      .then((payload) => {
        if (active) {
          setDetail({ kind: "loaded", item: payload.item });
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setDetail({
            kind: "error",
            message: error instanceof Error ? error.message : "Move detail unavailable."
          });
        }
      });
    return () => {
      active = false;
    };
  }, [leagueId, selectedId, session]);

  return (
    <section className="product-stack">
      <LeagueNav leagueId={leagueId} />
      <ProductHeader
        eyebrow={data.modelName}
        leagueId={leagueId}
        title="Waiver and free-agent browser"
      >
        <StatusPill tone="info">Current version</StatusPill>
      </ProductHeader>
      <MetricStrip
        metrics={[
          {
            label: "Visible moves",
            value: visibleRows.length.toString(),
            detail: "Filtered waiver and free-agent rows from the snapshot."
          },
          {
            label: "Score eligible",
            value: data.rows
              .filter((row) => booleanField(row, "scoreEligible") === true)
              .length.toString(),
            detail: "Only resolved add/drop impact contributes to waiver scores."
          },
          {
            label: "Caveated rows",
            value: data.rows.filter((row) => rowCaveats(row).length > 0).length.toString(),
            detail: "Unresolved points remain visible and excluded where required."
          }
        ]}
      />
      <WaiverSuperlativeHeader
        data={data.waiverSuperlatives[superlativeSeason]}
        season={superlativeSeason}
      />
      <FilterBar
        controller={filter}
        facets={facets}
        searchPlaceholder="Search managers or players…"
        sorts={WAIVER_SORTS}
        total={data.rows.length}
      />
      <section className="product-grid">
        <MoveTable onSelect={setSelectedId} rows={visibleRows} selectedId={selectedId} />
        <MoveDetail detail={detail} fallback={selectedRow} />
      </section>
    </section>
  );
}
