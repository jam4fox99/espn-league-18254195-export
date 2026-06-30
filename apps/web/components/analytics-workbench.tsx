"use client";

import Link from "next/link";
import { asideCopyFor, introFor, workspaceTitle } from "@/components/analytics-workbench-copy";
import { type AnalyticsKind, summaryMetrics } from "@/components/analytics-workbench-data";
import { type DetailRow, detailRowsFor } from "@/components/analytics-workbench-details";
import { InsightDeck, Workbench } from "@/components/product-insights";
import type { AnalyticsData } from "@/lib/product-api";
import { fixtureIds } from "@/lib/product-copy";

export type { AnalyticsKind };

export function AnalyticsWorkbench({
  analytics,
  kind,
  leagueId
}: {
  readonly analytics: AnalyticsData;
  readonly kind: AnalyticsKind;
  readonly leagueId: string;
}) {
  const row = analytics.rows[0];
  const copy = asideCopyFor(kind, analytics.sourceCoverage);
  return (
    <>
      <InsightDeck items={summaryMetrics(kind, analytics, row)} />
      <Workbench
        aside={<Aside kind={kind} leagueId={leagueId} lines={copy.lines} title={copy.title} />}
        intro={introFor(kind)}
        title={workspaceTitle(kind)}
      >
        <DetailTable rows={detailRowsFor(kind, row, analytics.sourceCoverage)} />
      </Workbench>
    </>
  );
}

function DetailTable({ rows }: { readonly rows: readonly DetailRow[] }) {
  return (
    <table className="detail-table">
      <tbody>
        {rows.map((row) => (
          <tr key={row.label}>
            <th scope="row">{row.label}</th>
            <td>
              <strong>{row.value}</strong>
              <p>{row.detail}</p>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Aside({
  kind,
  leagueId,
  lines,
  title
}: {
  readonly kind: AnalyticsKind;
  readonly leagueId: string;
  readonly lines: readonly string[];
  readonly title: string;
}) {
  return (
    <div className="workspace-panel bare-panel">
      <p className="section-kicker">Interpretation</p>
      <h2>{title}</h2>
      <ul className="plain-list">
        {uniqueLines(lines).map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      {kind === "gms" ? (
        <Link
          className="secondary-action fit-action"
          href={`/leagues/${leagueId}/gms/${fixtureIds.managerId}`}
        >
          Open manager report card
        </Link>
      ) : null}
    </div>
  );
}

function uniqueLines(lines: readonly string[]): readonly string[] {
  return [...new Set(lines)];
}
