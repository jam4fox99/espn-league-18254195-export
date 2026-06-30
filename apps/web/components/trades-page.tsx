"use client";

import { useMemo } from "react";
import { type Facet, FilterBar, type SortOption, useFacetFilter } from "@/components/controls";
import { LeagueNav, MetricStrip, ProductHeader } from "@/components/product-chrome";
import { ProductLoader } from "@/components/product-loader";
import { StatusPill } from "@/components/status-pill";
import {
  TradeList,
  tradeGradeBucket,
  tradeSearchText,
  tradeVetoBand
} from "@/components/trades-page-parts";
import {
  hasTradeSides,
  managerOptions,
  managersForRow,
  numberField,
  type SnapshotRow,
  seasonOptions,
  stringField,
  tradeSides
} from "@/components/transaction-page-utils";
import { readSnapshotRows, type SnapshotRowsData } from "@/lib/product-api";
import type { AlphaSession } from "@/lib/session";

const GRADE_OPTIONS = ["A", "B", "C", "D", "F"].map((grade) => ({ value: grade, label: grade }));

const TRADE_SORTS: readonly SortOption<SnapshotRow>[] = [
  {
    value: "newest",
    label: "Newest",
    compare: (left, right) =>
      (numberField(right, "season") ?? 0) - (numberField(left, "season") ?? 0) ||
      (numberField(right, "week") ?? 0) - (numberField(left, "week") ?? 0)
  },
  {
    value: "best",
    label: "Best value",
    compare: (left, right) =>
      (numberField(right, "netPoints") ?? 0) - (numberField(left, "netPoints") ?? 0)
  },
  {
    value: "lopsided",
    label: "Most lopsided",
    compare: (left, right) =>
      Math.abs(numberField(right, "netPoints") ?? 0) - Math.abs(numberField(left, "netPoints") ?? 0)
  }
];

export function TradesPage({ leagueId }: { readonly leagueId: string }) {
  const load = (session: AlphaSession) =>
    readSnapshotRows(session, `v1/leagues/${leagueId}/trades?version=current`);

  return (
    <ProductLoader load={load}>
      {(data) => <TradesSurface data={data} leagueId={leagueId} />}
    </ProductLoader>
  );
}

function TradesSurface({
  data,
  leagueId
}: {
  readonly data: SnapshotRowsData;
  readonly leagueId: string;
}) {
  // Only trades whose participants/assets survived ESPN source resolution reach the
  // browser; the rest are counted as "incomplete" rather than shown as Unresolved.
  const attributedRows = useMemo(() => data.rows.filter(hasTradeSides), [data.rows]);
  const incompleteCount = data.rows.length - attributedRows.length;

  const facets = useMemo<readonly Facet<SnapshotRow>[]>(
    () => [
      {
        key: "manager",
        label: "Manager",
        options: managerOptions(attributedRows),
        valuesOf: (row) => managersForRow(row).map((manager) => manager.value)
      },
      {
        key: "grade",
        label: "Grade",
        options: GRADE_OPTIONS,
        valuesOf: (row) => {
          const bucket = tradeGradeBucket(stringField(row, "tradeGrade"));
          return bucket ? [bucket] : [];
        }
      },
      {
        key: "season",
        label: "Season",
        options: seasonOptions(attributedRows).map((season) => ({ value: season, label: season })),
        valuesOf: (row) => {
          const season = numberField(row, "season");
          return season === undefined ? [] : [String(season)];
        }
      },
      {
        key: "veto",
        label: "Veto band",
        options: vetoBandOptions(attributedRows),
        valuesOf: (row) => {
          const band = tradeVetoBand(row);
          return band ? [band] : [];
        }
      }
    ],
    [attributedRows]
  );

  const filter = useFacetFilter({
    rows: attributedRows,
    facets,
    sorts: TRADE_SORTS,
    searchText: tradeSearchText
  });

  const gradedCount = attributedRows.filter((row) => row["scoreEligible"] === true).length;
  const playerCount = attributedRows.reduce(
    (total, row) => total + tradeSides(row).reduce((sum, side) => sum + side.assets.length, 0),
    0
  );

  return (
    <section className="product-stack">
      <LeagueNav leagueId={leagueId} />
      <ProductHeader eyebrow="Trade analyzer" leagueId={leagueId} title="Trade browser">
        <StatusPill tone="info">All-time</StatusPill>
      </ProductHeader>
      <MetricStrip
        metrics={[
          {
            label: "Attributed trades",
            value: attributedRows.length.toString(),
            detail:
              incompleteCount > 0
                ? `${incompleteCount} early-season trade${incompleteCount === 1 ? "" : "s"} omitted — counterparty missing from the ESPN source.`
                : "Every trade resolved to its managers."
          },
          {
            label: "Graded for scoring",
            value: gradedCount.toString(),
            detail: "Trades with resolved post-trade points on both sides."
          },
          {
            label: "Players moved",
            value: playerCount.toString(),
            detail: "Total assets exchanged across attributed trades."
          }
        ]}
      />
      <FilterBar
        controller={filter}
        facets={facets}
        searchPlaceholder="Search managers or players…"
        sorts={TRADE_SORTS}
        total={attributedRows.length}
      />
      <TradeList rows={filter.filtered} />
    </section>
  );
}

function vetoBandOptions(
  rows: readonly SnapshotRow[]
): readonly { value: string; label: string }[] {
  const bands = new Set<string>();
  for (const row of rows) {
    const band = tradeVetoBand(row);
    if (band) {
      bands.add(band);
    }
  }
  return [...bands].sort().map((band) => ({ value: band, label: band }));
}
