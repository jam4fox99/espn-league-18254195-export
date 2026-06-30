"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { AmbientWash } from "@/components/ambient-wash";
import { LeaderboardRows } from "@/components/leaderboard-rows";
import { LeagueNav, MetricStrip, ProductHeader } from "@/components/product-chrome";
import { ActionGrid, formatNumber, InsightDeck, Workbench } from "@/components/product-insights";
import { ProductLoader } from "@/components/product-loader";
import { StatusPill } from "@/components/status-pill";
import type { DashboardData, ReprocessRunData } from "@/lib/product-api";
import {
  createAnalyticsReprocessRun,
  readAdminImportRuns,
  readDashboard,
  readReprocessRun
} from "@/lib/product-api";
import { factsFromDashboard, productFactStatus, scoreLine } from "@/lib/product-model";
import type { AlphaSession } from "@/lib/session";

type RecomputeState =
  | { readonly kind: "idle" }
  | { readonly kind: "submitting" }
  | { readonly kind: "queued"; readonly run: ReprocessRunData }
  | { readonly kind: "error"; readonly message: string };

export function LeagueDashboard({ leagueId }: { readonly leagueId: string }) {
  const load = useCallback((session: AlphaSession) => readDashboard(session, leagueId), [leagueId]);

  return (
    <ProductLoader load={load}>
      {(dashboard, session) => {
        const facts = factsFromDashboard(dashboard);
        const factStatus = productFactStatus(facts);
        return (
          <section className="product-stack">
            <AmbientWash />
            <LeagueNav leagueId={leagueId} />
            <ProductHeader
              eyebrow={dashboard.leagueName ?? "League dashboard"}
              leagueId={leagueId}
              title={dashboard.leagueName ?? "Retrospective GM Rating"}
            >
              <StatusPill tone={factStatus === "ready" ? "success" : "warning"}>
                {dashboard.importStatus}
              </StatusPill>
            </ProductHeader>
            <MetricStrip
              metrics={[
                {
                  label: facts.ratingLabel,
                  value: scoreLine(dashboard.compositeScore),
                  detail: "Retrospective value captured, not a projection."
                },
                {
                  label: "Snapshot version",
                  value: "Current",
                  detail: dashboard.generatedAt ?? "Current published analytics snapshot."
                },
                {
                  label: "Available seasons",
                  value:
                    dashboard.availableSeasons && dashboard.availableSeasons.length > 0
                      ? dashboard.availableSeasons.join(", ")
                      : "Unavailable",
                  detail: "All-time leaderboard is shown by default."
                }
              ]}
            />
            <section className="workspace-hero">
              <article className="workspace-copy">
                <p className="section-kicker">All-time leaderboard</p>
                <h2>GM results from the current snapshot</h2>
                <p>
                  Scores below come from the published snapshot for this league. Missing or withheld
                  components stay caveated instead of receiving replacement scores.
                </p>
                <SeasonLinks leagueId={leagueId} seasons={dashboard.availableSeasons ?? []} />
                <LeaderboardTable leagueId={leagueId} rows={dashboard.leaderboard ?? []} />
              </article>
              <aside className="workspace-panel">
                <p className="section-kicker">Import status</p>
                <h2>{dashboard.importStatus}</h2>
                <p>
                  Dashboard reads the current published snapshot. Manual recompute status appears
                  here when the shared reprocess API is available.
                </p>
                <ul className="plain-list">
                  <li>Formula version: {dashboard.formulaVersion ?? "Current"}</li>
                  <li>Trade rows: {formatNumber(facts.canonicalGradedTradeEvents)}</li>
                  <li>Ungraded executed accepts: {formatNumber(facts.ungradedExecutedAccepts)}</li>
                  <li>
                    {facts.careerExcludedSeasons.includes(2026)
                      ? "2026 excluded from career ratings"
                      : "No career season exclusions reported"}
                  </li>
                </ul>
                <RecomputeSnapshotAction leagueId={leagueId} session={session} />
              </aside>
            </section>
            <InsightDeck
              items={[
                {
                  label: "Player-week rows",
                  value: formatNumber(dashboard.sourceCounts?.playerWeekRows),
                  detail: "Weekly scoring rows available for retrospective player value.",
                  tone: "info"
                },
                {
                  label: "Waiver rows",
                  value: formatNumber(dashboard.counts?.waiverRows),
                  detail: "Acquisition rows the waiver surface can inspect.",
                  tone: "success"
                },
                {
                  label: "Free-agent rows",
                  value: formatNumber(dashboard.counts?.freeAgentRows),
                  detail: "Non-waiver acquisitions retained for context.",
                  tone: "success"
                },
                {
                  label: "Box score payloads",
                  value: formatNumber(dashboard.sourceCounts?.boxScorePayloads),
                  detail: "Matchup payloads available for records and scoring context.",
                  tone: "neutral"
                }
              ]}
            />
            <Workbench
              aside={
                <ul className="plain-list">
                  {(facts.caveats.length > 0
                    ? facts.caveats
                    : ["Data health caveats pending API field."]
                  ).map((caveat) => (
                    <li key={caveat}>{caveat}</li>
                  ))}
                </ul>
              }
              intro="Use the linked review surfaces to inspect where the score came from before sending a share card."
              title="Review surfaces ready for this league"
            >
              <ActionGrid
                items={[
                  {
                    href: `/leagues/${leagueId}/gms`,
                    label: "Compare GMs",
                    detail: "Open the all-time leaderboard and manager profile routes."
                  },
                  {
                    href: `/leagues/${leagueId}/trades`,
                    label: "Audit trades",
                    detail: "See canonical graded events and withheld accepts."
                  },
                  {
                    href: `/leagues/${leagueId}/waivers`,
                    label: "Audit waivers",
                    detail: "Inspect waiver and free-agent row coverage."
                  },
                  {
                    href: `/leagues/${leagueId}/data-health`,
                    label: "Check caveats",
                    detail: "Review withheld scores before trusting rankings."
                  }
                ]}
              />
            </Workbench>
          </section>
        );
      }}
    </ProductLoader>
  );
}

function RecomputeSnapshotAction({
  leagueId,
  session
}: {
  readonly leagueId: string;
  readonly session: AlphaSession;
}) {
  const [state, setState] = useState<RecomputeState>({ kind: "idle" });

  async function recomputeSnapshot() {
    setState({ kind: "submitting" });
    try {
      const imports = await readAdminImportRuns(session);
      const source = imports.runs
        .filter((run) => run.leagueId === leagueId)
        .sort((left, right) => right.createdAt.localeCompare(left.createdAt))[0];
      if (source === undefined) {
        setState({ kind: "error", message: "No source import run is available for this league." });
        return;
      }
      const created = await createAnalyticsReprocessRun(session, leagueId, source.runId);
      const run = await readReprocessRun(session, created.runId);
      setState({ kind: "queued", run });
    } catch (error) {
      setState({
        kind: "error",
        message: error instanceof Error ? error.message : "Recompute request failed."
      });
    }
  }

  return (
    <>
      <button
        className="secondary-action fit-action"
        disabled={state.kind === "submitting"}
        onClick={recomputeSnapshot}
        type="button"
      >
        Recompute snapshot
      </button>
      <p className="section-kicker">{recomputeStatusText(state)}</p>
    </>
  );
}

function recomputeStatusText(state: RecomputeState): string {
  switch (state.kind) {
    case "idle":
      return "Status: current snapshot displayed";
    case "submitting":
      return "Status: recompute request sending";
    case "queued":
      return `Status: ${state.run.status} · recompute requested`;
    case "error":
      return `Status: ${state.message}`;
    default:
      return assertNever(state);
  }
}

function SeasonLinks({
  leagueId,
  seasons
}: {
  readonly leagueId: string;
  readonly seasons: readonly number[];
}) {
  return (
    <nav className="league-nav" aria-label="Season selector">
      <Link href={`/leagues/${leagueId}/gms`}>All-time</Link>
      {seasons.map((season) => (
        <Link href={`/leagues/${leagueId}/seasons/${season}`} key={season}>
          {season}
        </Link>
      ))}
    </nav>
  );
}

function LeaderboardTable({
  leagueId,
  rows
}: {
  readonly leagueId: string;
  readonly rows: NonNullable<DashboardData["leaderboard"]>;
}) {
  return <LeaderboardRows leagueId={leagueId} rows={rows} />;
}

function assertNever(value: never): never {
  throw new Error(`Unhandled recompute state: ${JSON.stringify(value)}`);
}
