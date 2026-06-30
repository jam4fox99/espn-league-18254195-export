"use client";

import Link from "next/link";
import { useCallback } from "react";
import { AmbientWash } from "@/components/ambient-wash";
import { useManagerLogo } from "@/components/manager-logos-provider";
import { LeagueNav, MetricStrip, ProductHeader } from "@/components/product-chrome";
import { ProductLoader } from "@/components/product-loader";
import { StatusPill } from "@/components/status-pill";
import { TeamEmblem } from "@/components/team-emblem";
import type { HistorySeasonData, LeagueHistoryData } from "@/lib/product-api";
import { readHistory } from "@/lib/product-api";
import type { AlphaSession } from "@/lib/session";

export function LeagueHistory({ leagueId }: { readonly leagueId: string }) {
  const load = useCallback((session: AlphaSession) => readHistory(session, leagueId), [leagueId]);

  return (
    <ProductLoader load={load}>
      {(history) => (
        <section className="product-stack">
          <AmbientWash />
          <LeagueNav leagueId={leagueId} />
          <ProductHeader eyebrow="League history" title="The story so far" />
          <MetricStrip
            metrics={[
              {
                label: "Seasons on record",
                value: String(history.seasonCount),
                detail: `Span ${history.span}`
              },
              {
                label: "Title holders",
                value: String(history.champions.length),
                detail: "Unique champions across the league's history."
              },
              {
                label: "Most titles",
                value: mostTitlesValue(history),
                detail: "Leader of the championship count."
              }
            ]}
          />
          <ReigningHero history={history} leagueId={leagueId} />
          {history.champions.length > 1 ? <ChampionMarquee history={history} /> : null}
          {history.champions.length > 0 ? <ChampionRoll history={history} /> : null}
          <ol className="history-timeline">
            {history.seasons.map((season) => (
              <SeasonMilestone key={season.season} leagueId={leagueId} season={season} />
            ))}
          </ol>
        </section>
      )}
    </ProductLoader>
  );
}

/** Hero of the reigning champion — the most recent final season with a champion. */
function ReigningHero({
  history,
  leagueId
}: {
  readonly history: LeagueHistoryData;
  readonly leagueId: string;
}) {
  const logoFor = useManagerLogo();
  const reigning = [...history.seasons]
    .filter((season) => !season.isPartial && season.champion?.displayName)
    .sort((a, b) => b.season - a.season)[0];
  if (!reigning?.champion) {
    return null;
  }
  const champ = reigning.champion;
  return (
    <div className="gm-hero history-hero">
      <div className="gm-hero__tag">★ Reigning champion · {reigning.season}</div>
      <div className="history-hero__grid">
        <TeamEmblem
          logo={logoFor(champ.managerKey, reigning.season)}
          name={champ.teamName ?? champ.displayName ?? "Champion"}
          size={92}
        />
        <div className="history-hero__id">
          <div className="gm-hero__role">League champion</div>
          <h2 className="gm-hero__champ">{champ.displayName}</h2>
          {champ.teamName ? (
            <div className="gm-hero__team">&ldquo;{champ.teamName}&rdquo;</div>
          ) : null}
          {champ.managerKey ? (
            <Link
              className="gm-hero__cta"
              href={`/leagues/${leagueId}/gms/${encodeURIComponent(champ.managerKey)}`}
            >
              View profile →
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  );
}

/** Ambient reigning-GM marquee (landing only) — animation in the motion pass. */
function ChampionMarquee({ history }: { readonly history: LeagueHistoryData }) {
  const items = history.champions.flatMap((champion) => [
    `${champion.displayName} — ${champion.titles} ${champion.titles === 1 ? "title" : "titles"}`
  ]);
  const doubled = [...items, ...items];
  return (
    <div className="marquee" aria-hidden="true">
      <div className="marquee__track">
        {doubled.map((text, index) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: marquee duplicates items for a seamless loop.
          <span className="marquee__item" key={`${text}-${index}`}>
            <span className="marquee__dot">◆</span>
            {text}
          </span>
        ))}
      </div>
    </div>
  );
}

function ChampionRoll({ history }: { readonly history: LeagueHistoryData }) {
  const logoFor = useManagerLogo();
  return (
    <article className="product-panel">
      <p className="section-kicker">Trophy count</p>
      <ul className="champion-roll">
        {history.champions.map((champion) => (
          <li key={champion.managerKey} className="champion-chip">
            <TeamEmblem
              logo={logoFor(champion.managerKey)}
              name={champion.displayName ?? "Champion"}
              size={22}
            />
            <span className="champion-chip__name">{champion.displayName}</span>
            <span className="champion-chip__count">
              {champion.titles} {champion.titles === 1 ? "title" : "titles"}
            </span>
          </li>
        ))}
      </ul>
    </article>
  );
}

function SeasonMilestone({
  leagueId,
  season
}: {
  readonly leagueId: string;
  readonly season: HistorySeasonData;
}) {
  const logoFor = useManagerLogo();
  const championName = season.champion?.displayName;
  const championTeam = season.champion?.teamName;
  return (
    <li className="history-milestone">
      <div className="history-milestone__year">
        <span className="history-year">{season.season}</span>
        {season.isPartial ? (
          <StatusPill tone="info">In progress</StatusPill>
        ) : (
          <StatusPill tone="success">Final</StatusPill>
        )}
      </div>
      <div className="history-milestone__body">
        <Link
          className="history-milestone__title"
          href={`/leagues/${leagueId}/seasons/${season.season}`}
        >
          {season.headline}
        </Link>
        {championName ? (
          <p className="history-milestone__champ">
            <TeamEmblem
              logo={logoFor(season.champion?.managerKey, season.season)}
              name={championTeam ?? championName}
              size={20}
            />
            Champion: <strong>{championName}</strong>
            {championTeam ? ` · ${championTeam}` : ""}
          </p>
        ) : null}
        {season.superlatives.length > 0 ? (
          <ul className="history-receipts">
            {season.superlatives.map((superlative, index) => (
              <li key={`${season.season}-${superlative.label ?? index}`}>
                <span className="history-receipts__label">
                  {superlative.label ?? "Superlative"}
                </span>
                <span className="history-receipts__detail">
                  {superlative.detail ?? superlative.displayName ?? ""}
                </span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </li>
  );
}

function mostTitlesValue(history: LeagueHistoryData): string {
  const leader = history.champions[0];
  if (!leader || leader.titles === 0) {
    return "—";
  }
  return `${leader.displayName} (${leader.titles})`;
}
