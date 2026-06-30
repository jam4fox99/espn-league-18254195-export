"use client";

import { useCallback } from "react";
import { type LeaderboardRow, LeaderboardRows } from "@/components/leaderboard-rows";
import { useManagerLogo } from "@/components/manager-logos-provider";
import { PlayerChip } from "@/components/player-image";
import { LeagueNav, MetricStrip, ProductHeader } from "@/components/product-chrome";
import { ProductLoader } from "@/components/product-loader";
import { StatusPill } from "@/components/status-pill";
import { TeamEmblem } from "@/components/team-emblem";
import type { SeasonHubData, SeasonStandingRow } from "@/lib/product-api";
import { readSeasonHub } from "@/lib/product-api";
import type { AlphaSession } from "@/lib/session";

type DraftRecap = SeasonHubData["draftRecap"];
type DraftPickRef = NonNullable<DraftRecap["bestSteal"]>;

// Draft picks pass the player-chip identity fields through (snapshot enrich), but
// the ref schema only types playerName — read the rest defensively from the row.
function asNumber(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}
function asString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}
function asBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function draftPickChip(pick: DraftPickRef) {
  return {
    playerId: asNumber(pick["playerId"]),
    name: pick.playerName ?? "Player",
    teamAbbr: asString(pick["proTeamAbbrev"]),
    position: asString(pick["position"]),
    isDST: asBoolean(pick["isDST"])
  };
}

export function SeasonHub({
  leagueId,
  season
}: {
  readonly leagueId: string;
  readonly season: string;
}) {
  const load = useCallback(
    (session: AlphaSession) => readSeasonHub(session, leagueId, season),
    [leagueId, season]
  );

  return (
    <ProductLoader load={load}>
      {(hub) => (
        <section className="product-stack">
          <LeagueNav leagueId={leagueId} />
          <ProductHeader
            eyebrow={hub.isPartial ? "Season in progress" : "Season review"}
            title={`${hub.season} season`}
          />
          <SeasonChampionHero hub={hub} />
          <MetricStrip metrics={seasonMetrics(hub)} />
          {hub.review.length > 0 ? (
            <article className="product-panel">
              <p className="section-kicker">Season in review</p>
              <ul className="review-list">
                {hub.review.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </article>
          ) : null}
          {hub.finalStandings.length > 0 ? (
            <StandingsTable season={hub.season} standings={hub.finalStandings} />
          ) : null}
          {hub.ratings.length > 0 ? (
            <article className="product-panel">
              <p className="section-kicker">Season GM ratings</p>
              <LeaderboardRows leagueId={leagueId} rows={hub.ratings as LeaderboardRow[]} />
            </article>
          ) : null}
          <DraftRecapPanel recap={hub.draftRecap} />
        </section>
      )}
    </ProductLoader>
  );
}

/** The champion (and runner-up) as a true hero moment above the breakdown. */
function SeasonChampionHero({ hub }: { readonly hub: SeasonHubData }) {
  const logoFor = useManagerLogo();
  const champ = hub.champion;
  if (!champ?.displayName) {
    return null;
  }
  const runner = hub.runnerUp;
  return (
    <div className="gm-hero season-hero">
      <div className="gm-hero__tag">★ {hub.season} champion</div>
      <div className="season-hero__grid">
        <div className="season-hero__champ">
          <TeamEmblem
            logo={logoFor(champ.managerKey, hub.season)}
            name={champ.teamName ?? champ.displayName}
            size={96}
            you
          />
          <div className="history-hero__id">
            <div className="gm-hero__role">League champion</div>
            <h2 className="gm-hero__champ">{champ.displayName}</h2>
            {champ.teamName ? (
              <div className="gm-hero__team">&ldquo;{champ.teamName}&rdquo;</div>
            ) : null}
          </div>
        </div>
        {runner?.displayName ? (
          <div className="season-hero__runner">
            <div className="gm-hero__role">Runner-up</div>
            <div className="season-hero__runner-id">
              <TeamEmblem
                logo={logoFor(runner.managerKey, hub.season)}
                name={runner.teamName ?? runner.displayName}
                size={44}
              />
              <div className="season-hero__runner-meta">
                <span className="season-hero__runner-name">{runner.displayName}</span>
                {runner.teamName ? <small>{runner.teamName}</small> : null}
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function seasonMetrics(hub: SeasonHubData) {
  const base = [
    {
      label: "Playoff teams",
      value: `${hub.playoffTeamCount ?? "—"}`,
      detail: hub.finalWeek ? `Final week ${hub.finalWeek}.` : "Postseason field."
    },
    {
      label: "Roster moves",
      value: `${hub.transactionCount ?? "—"}`,
      detail: "Trades, waivers, and free-agent adds."
    }
  ];
  // When a champion is crowned, the hero above already celebrates the title race,
  // so the strip stays focused on season volume. Partial seasons fall back to the
  // champion/runner-up placeholders.
  if (hub.champion?.displayName) {
    return base;
  }
  return [
    {
      label: "Champion",
      value: hub.isPartial ? "TBD" : "—",
      detail: "League champion."
    },
    {
      label: "Runner-up",
      value: hub.runnerUp?.displayName ?? "—",
      detail: "Lost in the championship."
    },
    ...base
  ];
}

function StandingsTable({
  season,
  standings
}: {
  readonly season: number | undefined;
  readonly standings: readonly SeasonStandingRow[];
}) {
  const logoFor = useManagerLogo();
  const ordered = [...standings].sort((a, b) => (a.rankFinal ?? 99) - (b.rankFinal ?? 99));
  return (
    <article className="product-panel">
      <p className="section-kicker">Final standings</p>
      <ul className="standings-table">
        <li className="standings-row standings-row--head">
          <span>#</span>
          <span>Manager</span>
          <span>Record</span>
          <span>PF</span>
          <span>Result</span>
        </li>
        {ordered.map((row) => (
          <li key={row.managerKey ?? row.displayName ?? row.rankFinal} className="standings-row">
            <span className="standings-row__rank">{row.rankFinal ?? "—"}</span>
            <span className="standings-row__name">
              <TeamEmblem
                logo={logoFor(row.managerKey, season)}
                name={row.teamName ?? row.displayName ?? "Manager"}
                size={28}
                you={row.isChampion === true}
              />
              <span className="standings-row__ident">
                {row.displayName ?? "Manager"}
                {row.teamName ? <small>{row.teamName}</small> : null}
              </span>
            </span>
            <span className="standings-row__record">
              {row.wins ?? 0}-{row.losses ?? 0}
              {row.ties ? `-${row.ties}` : ""}
            </span>
            <span className="standings-row__points">{(row.pointsFor ?? 0).toFixed(1)}</span>
            <span className="standings-row__result">
              {row.isChampion ? (
                <StatusPill tone="success">Champion</StatusPill>
              ) : row.madePlayoffs ? (
                <StatusPill tone="info">Playoffs</StatusPill>
              ) : (
                ""
              )}
            </span>
          </li>
        ))}
      </ul>
    </article>
  );
}

function DraftRecapPanel({ recap }: { readonly recap: DraftRecap }) {
  const steal = recap.bestSteal;
  const bust = recap.biggestBust;
  if (!steal && !bust) {
    return null;
  }
  return (
    <article className="product-panel">
      <p className="section-kicker">Draft recap</p>
      <div className="franchise-grid">
        {steal ? (
          <div className="draft-card draft-card--steal">
            <span className="draft-card__tag">Steal of the draft</span>
            <div className="draft-card__player">
              <PlayerChip {...draftPickChip(steal)} size={38} />
            </div>
            <p className="draft-card__detail">
              {steal.displayName ?? "Manager"} · pick {steal.overallPick ?? "—"} · finished #
              {steal.pointsRank ?? "—"}
            </p>
          </div>
        ) : null}
        {bust ? (
          <div className="draft-card draft-card--bust">
            <span className="draft-card__tag">Biggest bust</span>
            <div className="draft-card__player">
              <PlayerChip {...draftPickChip(bust)} size={38} />
            </div>
            <p className="draft-card__detail">
              {bust.displayName ?? "Manager"} · pick {bust.overallPick ?? "—"} · finished #
              {bust.pointsRank ?? "—"}
            </p>
          </div>
        ) : null}
      </div>
    </article>
  );
}
