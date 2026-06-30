"use client";

import type { Route } from "next";
import Link from "next/link";
import { type CSSProperties, useCallback, useState } from "react";
import { AliasGrid } from "@/components/alias-grid";
import { AnalyticsWorkbench } from "@/components/analytics-workbench";
import { GmRatingsBoard } from "@/components/gm-ratings-board";
import type { LeaderboardRow } from "@/components/leaderboard-rows";
import { useManagerLogo } from "@/components/manager-logos-provider";
import { LeagueNav, MetricStrip, ProductHeader } from "@/components/product-chrome";
import { ProductLoader } from "@/components/product-loader";
import { archetypeColor } from "@/lib/images";
import type { AnalyticsData, ManagerReportData } from "@/lib/product-api";
import { readAnalytics, readManagerReport } from "@/lib/product-api";
import { analyticsScore, managerTitle, scoreLine } from "@/lib/product-model";
import type { AlphaSession } from "@/lib/session";

type ArchetypeStyle = CSSProperties & { "--arch": string };

const HISTORIAN_FORMULA = "mygm-historian-v2";
const LEGACY_FORMULA = "mygm-retrospective-v1";

const FORMULA_OPTIONS = [
  { id: HISTORIAN_FORMULA, label: "Historian v2" },
  { id: LEGACY_FORMULA, label: "Legacy v1" }
] as const;

export function AnalyticsPage({
  leagueId,
  kind,
  seasonYear
}: {
  readonly leagueId: string;
  readonly kind: "season" | "gms" | "trades" | "waivers" | "records";
  readonly seasonYear?: string;
}) {
  const load = useCallback(
    (session: AlphaSession) => readAnalytics(session, analyticsPath(leagueId, kind, seasonYear)),
    [kind, leagueId, seasonYear]
  );

  return (
    <ProductLoader load={load}>
      {(analytics) => (
        <section className="product-stack">
          <LeagueNav leagueId={leagueId} />
          <ProductHeader eyebrow={analytics.modelName} leagueId={leagueId} title={titleFor(kind)} />
          <MetricStrip
            metrics={[
              {
                label: "Retrospective GM Rating",
                value: scoreLine(analyticsScore(analytics)),
                detail: "Historical value captured with confidence and source coverage."
              },
              {
                label: "Formula version",
                value: "Current",
                detail: analytics.sourceCoverage
              },
              {
                label: "Confidence",
                value: analytics.confidence,
                detail: "Shown beside every ranked surface."
              }
            ]}
          />
          {kind === "gms" ? (
            <GmLeaderboard analytics={analytics} leagueId={leagueId} />
          ) : (
            <AnalyticsWorkbench analytics={analytics} kind={kind} leagueId={leagueId} />
          )}
        </section>
      )}
    </ProductLoader>
  );
}

export function GmRatingsPage({ leagueId }: { readonly leagueId: string }) {
  const [formula, setFormula] = useState<string>(HISTORIAN_FORMULA);
  const load = useCallback(
    (session: AlphaSession) =>
      readAnalytics(
        session,
        `v1/leagues/${leagueId}/gms?scope=all_time&version=current&formula=${formula}`
      ),
    [formula, leagueId]
  );

  return (
    <section className="product-stack">
      <LeagueNav leagueId={leagueId} />
      <ProductHeader eyebrow="GM rating" leagueId={leagueId} title="GM leaderboard" />
      <div className="formula-toggle">
        {FORMULA_OPTIONS.map((option) => (
          <button
            key={option.id}
            type="button"
            className="formula-toggle__option"
            data-active={option.id === formula}
            aria-pressed={option.id === formula}
            onClick={() => setFormula(option.id)}
          >
            {option.label}
          </button>
        ))}
      </div>
      <p className="muted-note">
        {formula === LEGACY_FORMULA
          ? "Legacy v1 trade and waiver components are league-wide constants and are kept only for comparison."
          : "Historian v2: trade value, waiver/FA value, lineup efficiency, and record & points. Luck is excluded."}
      </p>
      <ProductLoader load={load}>
        {(analytics) => <GmLeaderboard analytics={analytics} leagueId={leagueId} />}
      </ProductLoader>
    </section>
  );
}

export function ManagerReport({
  leagueId,
  managerId
}: {
  readonly leagueId: string;
  readonly managerId: string;
}) {
  const load = useCallback(
    (session: AlphaSession) => readManagerReport(session, leagueId, managerId),
    [leagueId, managerId]
  );

  return (
    <ProductLoader load={load}>
      {(report) => (
        <section className="product-stack">
          <LeagueNav leagueId={leagueId} />
          <ProductHeader
            eyebrow="Manager report card"
            leagueId={leagueId}
            title={managerTitle(report)}
          />
          {report.archetype?.name ? (
            <div
              className="report-archetype"
              style={{ "--arch": archetypeColor(report.archetype.name) } as ArchetypeStyle}
            >
              <span className="report-archetype__badge">{report.archetype.name}</span>
              {report.archetype.oneLiner ? (
                <p className="report-archetype__line">{report.archetype.oneLiner}</p>
              ) : null}
            </div>
          ) : null}
          <MetricStrip
            metrics={[
              {
                label: "Retrospective GM Rating",
                value: scoreLine(report.compositeScore),
                detail:
                  report.scoreEligible === false ? "Score withheld or partial" : report.confidence
              },
              {
                label: "Aliases",
                value: aliasLine(report),
                detail: "Season team aliases resolved from the snapshot."
              },
              {
                label: "Formula version",
                value: report.version,
                detail: "No projections or future advice."
              }
            ]}
          />
          <ManagerProfileDetails report={report} />
          <nav className="profile-links" aria-label="Manager links">
            <Link
              className="profile-links__item"
              href={
                `/leagues/${leagueId}/managers/${encodeURIComponent(report.managerKey ?? managerId)}` as Route
              }
            >
              View franchise history →
            </Link>
            <Link className="profile-links__item" href={`/leagues/${leagueId}/formula` as Route}>
              How the rating works →
            </Link>
          </nav>
        </section>
      )}
    </ProductLoader>
  );
}

function analyticsPath(
  leagueId: string,
  kind: AnalyticsPagePropsKind,
  seasonYear?: string
): string {
  switch (kind) {
    case "season":
      return `v1/leagues/${leagueId}/seasons/${seasonYear ?? "2025"}?version=current`;
    case "gms":
      return `v1/leagues/${leagueId}/gms?scope=all_time&version=current`;
    case "trades":
      return `v1/leagues/${leagueId}/trades?version=current`;
    case "waivers":
      return `v1/leagues/${leagueId}/waivers?version=current`;
    case "records":
      return `v1/leagues/${leagueId}/records?version=current`;
    default:
      return assertNever(kind);
  }
}

type AnalyticsPagePropsKind = "season" | "gms" | "trades" | "waivers" | "records";

function titleFor(kind: AnalyticsPagePropsKind): string {
  switch (kind) {
    case "season":
      return "Season overview";
    case "gms":
      return "GM leaderboard";
    case "trades":
      return "Trade grades";
    case "waivers":
      return "Waiver grades";
    case "records":
      return "All-time records";
    default:
      return assertNever(kind);
  }
}

function assertNever(value: never): never {
  throw new Error(`Unhandled analytics page kind: ${value}`);
}

function GmLeaderboard({
  analytics,
  leagueId
}: {
  readonly analytics: AnalyticsData;
  readonly leagueId: string;
}) {
  const rows: LeaderboardRow[] = analytics.rows.map((row) => {
    const leaderboardRow = row.leaderboard?.[0];
    return {
      managerKey: leaderboardRow?.managerKey ?? row.productLabel ?? row.leagueId,
      rank: leaderboardRow?.rank,
      managerName: leaderboardRow?.managerName,
      displayName: leaderboardRow?.displayName ?? row.productLabel,
      teamName: leaderboardRow?.teamName,
      score: leaderboardRow?.score ?? row.compositeScore,
      scoreEligible: leaderboardRow?.scoreEligible,
      componentBreakdown: leaderboardRow?.componentBreakdown ?? leaderboardRow?.components,
      caveats: [...(leaderboardRow?.caveats ?? []), ...(row.caveats ?? [])],
      logo: leaderboardRow?.logo,
      signaturePlayer: leaderboardRow?.signaturePlayer,
      archetype: leaderboardRow?.archetype
    };
  });
  return <GmRatingsBoard leagueId={leagueId} rows={rows} />;
}

function ManagerProfileDetails({ report }: { readonly report: ManagerReportData }) {
  const logoFor = useManagerLogo();
  const managerKey = report.managerKey ?? report.managerId;
  return (
    <section className="workspace-hero">
      <article className="workspace-copy">
        <p className="section-kicker">Component breakdown</p>
        <h2>Score inputs</h2>
        <ComponentBreakdown components={report.componentBreakdown} />
        <CaveatList caveats={report.caveats ?? []} />
      </article>
      <aside className="workspace-panel">
        <p className="section-kicker">Profile context</p>
        <h2>Team identities by season</h2>
        <AliasGrid
          aliases={report.teamAliases ?? []}
          logoOf={(season) => (managerKey ? logoFor(managerKey, season) : null)}
        />
        <h2>Best and worst moves</h2>
        <ul className="plain-list">
          {(report.bestMoves ?? []).map((move) => (
            <li key={move.label ?? move.detail ?? "best-move"}>
              {move.label ?? "Best move"}: {move.detail ?? scoreLine(move.value)}
            </li>
          ))}
          {(report.worstMoves ?? []).map((move) => (
            <li key={move.label ?? move.detail ?? "worst-move"}>
              {move.label ?? "Worst move"}: {move.detail ?? scoreLine(move.value)}
            </li>
          ))}
        </ul>
      </aside>
    </section>
  );
}

function ComponentBreakdown({
  components
}: {
  readonly components: ManagerReportData["componentBreakdown"];
}) {
  const entries = Object.entries(components);
  if (entries.length === 0) {
    return <p>No component breakdown reported.</p>;
  }

  return (
    <ul className="score-bars">
      {entries.map(([key, component]) => {
        const value = component.score ?? component.value;
        const withheld = value === null || value === undefined;
        const pct = withheld ? 100 : Math.max(2, Math.min(100, Number(value)));
        return (
          <li key={key} className={`score-bar${withheld ? " is-withheld" : ""}`}>
            <div className="score-bar__top">
              <span className="score-bar__label">
                {component.label ?? key}
                {component.weight === undefined ? null : (
                  <span className="weight-tag">
                    {" "}
                    · {Math.round(Number(component.weight) * 100)}%
                  </span>
                )}
              </span>
              <span className="score-bar__value">{withheld ? "Withheld" : scoreLine(value)}</span>
            </div>
            <div className="score-bar__track">
              <div className="score-bar__fill" style={{ width: `${pct}%` }} />
            </div>
            {(component.caveats ?? []).length > 0 ? (
              <CaveatList caveats={component.caveats ?? []} />
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

function CaveatList({ caveats }: { readonly caveats: readonly string[] }) {
  if (caveats.length === 0) {
    return <p>No caveats reported.</p>;
  }

  return (
    <ul className="plain-list">
      {caveats.map((caveat) => (
        <li key={caveat}>{caveat}</li>
      ))}
    </ul>
  );
}

function aliasLine(report: ManagerReportData): string {
  const aliases = report.teamAliases ?? [];
  if (aliases.length === 0) {
    return "No aliases reported";
  }
  return aliases
    .map((alias) => `${alias.season ?? "season"} ${alias.teamName ?? alias.teamId ?? "team"}`)
    .join(", ");
}
