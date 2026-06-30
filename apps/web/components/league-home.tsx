"use client";

import {
  CalendarRange,
  Flame,
  Layers,
  type LucideIcon,
  Scale,
  Sparkles,
  Trophy
} from "lucide-react";
import Link from "next/link";
import { useCallback } from "react";
import { AmbientWash } from "@/components/ambient-wash";
import { LeaderboardRows } from "@/components/leaderboard-rows";
import { useManagerLogo } from "@/components/manager-logos-provider";
import { LeagueNav, MetricStrip, ProductHeader } from "@/components/product-chrome";
import { ProductLoader } from "@/components/product-loader";
import { TeamEmblem } from "@/components/team-emblem";
import type { DashboardData, LeagueHistoryData, RecordBookData } from "@/lib/product-api";
import { readDashboard, readHistory, readRecordBook } from "@/lib/product-api";
import type { AlphaSession } from "@/lib/session";

type HomeData = {
  readonly history: LeagueHistoryData;
  readonly dashboard: DashboardData;
  readonly recordBook: RecordBookData;
};

export function LeagueHome({ leagueId }: { readonly leagueId: string }) {
  const load = useCallback(
    async (session: AlphaSession): Promise<HomeData> => {
      const [history, dashboard, recordBook] = await Promise.all([
        readHistory(session, leagueId),
        readDashboard(session, leagueId),
        readRecordBook(session, leagueId)
      ]);
      return { history, dashboard, recordBook };
    },
    [leagueId]
  );

  return (
    <ProductLoader load={load}>
      {({ history, dashboard, recordBook }) => {
        const leaders = dashboard.leaderboard ?? [];
        return (
          <section className="product-stack">
            <AmbientWash />
            <LeagueNav leagueId={leagueId} />
            <ProductHeader eyebrow="League home" title={dashboard.leagueName ?? "Home base"} />
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
                  detail: "Unique champions in league history."
                },
                {
                  label: "Trophies awarded",
                  value: String(history.champions.reduce((sum, c) => sum + c.titles, 0)),
                  detail: "Championships across every final season."
                }
              ]}
            />
            <ReigningChampionHero history={history} leagueId={leagueId} />
            <div className="home-split">
              <article className="product-panel">
                <div className="panel-head">
                  <p className="section-kicker">GM leaderboard</p>
                  <Link className="panel-head__link" href={`/leagues/${leagueId}/gms`}>
                    Full GM Ratings →
                  </Link>
                </div>
                {leaders.length > 0 ? (
                  <LeaderboardRows leagueId={leagueId} rows={leaders.slice(0, 6)} compact />
                ) : (
                  <p className="muted-note">No leaderboard rows are available for this snapshot.</p>
                )}
              </article>
              <aside className="product-panel">
                <p className="section-kicker">League news</p>
                <NewsFeed history={history} recordBook={recordBook} />
              </aside>
            </div>
            {history.champions.length > 0 ? (
              <TrophyCount history={history} leagueId={leagueId} />
            ) : null}
          </section>
        );
      }}
    </ProductLoader>
  );
}

/** Reigning champion — most recent final season with a champion, as a hero. */
function ReigningChampionHero({
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
  const champ = reigning?.champion;
  if (!reigning || !champ?.managerKey) {
    return null;
  }
  return (
    <div className="gm-hero history-hero">
      <div className="gm-hero__tag">★ Reigning champion · {reigning.season}</div>
      <div className="history-hero__grid">
        <TeamEmblem
          logo={logoFor(champ.managerKey, reigning.season)}
          name={champ.teamName ?? champ.displayName ?? "Champion"}
          size={92}
          you
        />
        <div className="history-hero__id">
          <div className="gm-hero__role">League champion</div>
          <h2 className="gm-hero__champ">{champ.displayName}</h2>
          {champ.teamName ? (
            <div className="gm-hero__team">&ldquo;{champ.teamName}&rdquo;</div>
          ) : null}
          <Link
            className="gm-hero__cta"
            href={`/leagues/${leagueId}/gms/${encodeURIComponent(champ.managerKey)}`}
          >
            View profile →
          </Link>
        </div>
      </div>
    </div>
  );
}

function TrophyCount({
  history,
  leagueId
}: {
  readonly history: LeagueHistoryData;
  readonly leagueId: string;
}) {
  const logoFor = useManagerLogo();
  return (
    <article className="product-panel">
      <p className="section-kicker">Trophy count</p>
      <ul className="champion-roll">
        {history.champions.map((champion) => (
          <li key={champion.managerKey} className="champion-chip">
            <Link
              className="champion-chip__link"
              href={`/leagues/${leagueId}/gms/${encodeURIComponent(champion.managerKey)}`}
            >
              <TeamEmblem
                logo={logoFor(champion.managerKey)}
                name={champion.displayName ?? "Champion"}
                size={22}
              />
              <span className="champion-chip__name">{champion.displayName}</span>
              <span className="champion-chip__count">
                {champion.titles} {champion.titles === 1 ? "title" : "titles"}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </article>
  );
}

/* -------------------------------------------------------- League news feed */

type FeedTone = "gold" | "green" | "blue" | "neutral";

type FeedItem = {
  readonly key: string;
  readonly kind: string;
  readonly season?: number | undefined;
  readonly text: string;
  readonly detail?: string | undefined;
  readonly tone: FeedTone;
  readonly icon: LucideIcon;
};

function formatRecordValue(value: string | number): string {
  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toString() : value.toFixed(1);
  }
  return value;
}

function recordHolder(row: RecordBookData["rows"][number]): string | undefined {
  const parts = [row.managerName, row.teamName].filter(Boolean) as string[];
  const who = parts.join(" · ");
  if (row.season) {
    return who ? `${who} · ${row.season}` : `${row.season}`;
  }
  return who || undefined;
}

/** Auto-generated activity feed from existing snapshot data (no authoring). */
function buildFeed(history: LeagueHistoryData, recordBook: RecordBookData): FeedItem[] {
  const items: FeedItem[] = [];
  const finalSeasons = [...history.seasons]
    .filter((season) => !season.isPartial && season.champion?.displayName)
    .sort((a, b) => b.season - a.season);

  const reigning = finalSeasons[0];
  if (reigning?.champion?.displayName) {
    items.push({
      key: `champ-${reigning.season}`,
      kind: "Champion crowned",
      season: reigning.season,
      text: `${reigning.champion.displayName} won the ${reigning.season} championship`,
      detail: reigning.champion.teamName ? `Team: ${reigning.champion.teamName}` : undefined,
      tone: "gold",
      icon: Trophy
    });
  }

  // Track the concepts already surfaced so season notes don't repeat a record.
  const seen = new Set<string>();
  const normalize = (text: string) => text.toLowerCase().replace(/[^a-z]/g, "");

  const byCategory = new Map(recordBook.rows.map((row) => [row.category, row]));
  const recordPicks: ReadonlyArray<{
    readonly category: string;
    readonly kind: string;
    readonly tone: FeedTone;
    readonly icon: FeedItem["icon"];
  }> = [
    { category: "best_trade", kind: "Trade of the year", tone: "blue", icon: Scale },
    { category: "best_pickup", kind: "Waiver pickup", tone: "green", icon: Layers },
    { category: "waiver_value_leader", kind: "Waiver value", tone: "green", icon: Layers },
    { category: "highest_weekly_score", kind: "Record set", tone: "gold", icon: Flame },
    { category: "most_season_points", kind: "Record set", tone: "gold", icon: Flame },
    { category: "draft_steal", kind: "Draft steal", tone: "green", icon: Sparkles }
  ];
  for (const pick of recordPicks) {
    const row = byCategory.get(pick.category);
    if (!row) {
      continue;
    }
    seen.add(normalize(pick.kind));
    items.push({
      key: `rec-${pick.category}`,
      kind: pick.kind,
      season: row.season ?? undefined,
      text: `${row.label} — ${formatRecordValue(row.value)}`,
      detail: recordHolder(row),
      tone: pick.tone,
      icon: pick.icon
    });
  }

  // Recent-season color: each distinct superlative once, skipping anything a
  // record above already covers (e.g. a per-season "Draft steal").
  let seasonNotes = 0;
  for (const season of finalSeasons) {
    if (seasonNotes >= 3) {
      break;
    }
    const superlative = season.superlatives.find(
      (sup) => sup.label && sup.detail && !seen.has(normalize(sup.label))
    );
    if (superlative?.label) {
      seen.add(normalize(superlative.label));
      seasonNotes += 1;
      items.push({
        key: `season-${season.season}-${superlative.label}`,
        kind: "Season note",
        season: season.season,
        text: superlative.label,
        detail: superlative.detail ?? superlative.displayName ?? undefined,
        tone: "neutral",
        icon: CalendarRange
      });
    }
  }

  return items.slice(0, 9);
}

function NewsFeed({
  history,
  recordBook
}: {
  readonly history: LeagueHistoryData;
  readonly recordBook: RecordBookData;
}) {
  const items = buildFeed(history, recordBook);
  if (items.length === 0) {
    return <p className="muted-note">No league activity is available for this snapshot yet.</p>;
  }
  return (
    <ul className="news-feed">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <li key={item.key} className={`news-item news-item--${item.tone}`}>
            <span className="news-item__icon" aria-hidden="true">
              <Icon size={15} />
            </span>
            <span className="news-item__body">
              <span className="news-item__head">
                <span className="news-item__kind">{item.kind}</span>
                {item.season ? <span className="news-item__season">{item.season}</span> : null}
              </span>
              <span className="news-item__text">{item.text}</span>
              {item.detail ? <span className="news-item__detail">{item.detail}</span> : null}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
