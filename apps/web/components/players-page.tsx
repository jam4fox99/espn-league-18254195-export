"use client";

import { useCallback, useMemo } from "react";
import { type Facet, FilterBar, filterRows, useFacetFilter } from "@/components/controls";
import { PlayerChip } from "@/components/player-image";
import { LeagueNav, ProductHeader } from "@/components/product-chrome";
import { ProductLoader } from "@/components/product-loader";
import { medalColor } from "@/lib/images";
import type {
  LineupEfficiencyRow,
  PlayerDirectory,
  PlayerLeaderboardsData,
  PlayerSeasonRow,
  PlayerWeekRow
} from "@/lib/product-api";
import { readPlayerLeaderboards } from "@/lib/product-api";
import type { AlphaSession } from "@/lib/session";

type PlayerBoardRow = PlayerWeekRow | PlayerSeasonRow;

function playerSearchText(row: PlayerBoardRow): string {
  return row.playerName;
}

function distinct(values: readonly string[]): readonly string[] {
  return [...new Set(values.filter((value) => value.length > 0))].sort();
}

interface ResolvedPlayer {
  readonly playerId: number | null;
  readonly teamAbbr: string | null;
  readonly position: string;
  readonly isDST: boolean;
  readonly badge: string | null;
}

/** Resolve a player's chip fields from the row, backfilled by the directory. */
function resolvePlayer(
  row: {
    playerId?: number | null | undefined;
    proTeamAbbrev?: string | undefined;
    isDST?: boolean | undefined;
    position?: string | undefined;
    badge?: string | undefined;
  },
  directory: PlayerDirectory
): ResolvedPlayer {
  const id = row.playerId ?? null;
  const dir = id != null ? directory[String(id)] : undefined;
  return {
    playerId: id,
    teamAbbr: row.proTeamAbbrev ?? dir?.proTeamAbbrev ?? null,
    position: row.position || dir?.position || "",
    isDST: row.isDST ?? dir?.isDST ?? (id != null && id < 0),
    badge: row.badge ?? dir?.badge ?? null
  };
}

/** Rank cell: top-3 ranks render in their medal color; #1 also gets weight. */
function BoardRank({ index }: { readonly index: number }) {
  const rank = index + 1;
  const medal = medalColor(rank);
  const classes = ["player-board__rank"];
  if (medal) {
    classes.push("player-board__rank--medal");
  }
  return (
    <span className={classes.join(" ")} style={medal ? { color: medal } : undefined}>
      {rank}
    </span>
  );
}

export function PlayersPage({ leagueId }: { readonly leagueId: string }) {
  const load = useCallback(
    (session: AlphaSession) => readPlayerLeaderboards(session, leagueId),
    [leagueId]
  );

  return (
    <ProductLoader load={load}>
      {(data) => <PlayersSurface data={data} leagueId={leagueId} />}
    </ProductLoader>
  );
}

function PlayersSurface({
  data,
  leagueId
}: {
  readonly data: PlayerLeaderboardsData;
  readonly leagueId: string;
}) {
  const facets = useMemo<readonly Facet<PlayerBoardRow>[]>(() => {
    const all: PlayerBoardRow[] = [...data.topWeeks, ...data.topSeasons];
    const toOptions = (values: readonly string[]) =>
      values.map((value) => ({ value, label: value }));
    return [
      {
        key: "position",
        label: "Position",
        options: toOptions(distinct(all.map((row) => row.position))),
        valuesOf: (row) => (row.position ? [row.position] : [])
      },
      {
        key: "manager",
        label: "Manager",
        options: toOptions(distinct(all.map((row) => row.displayName))),
        valuesOf: (row) => (row.displayName ? [row.displayName] : [])
      },
      {
        key: "season",
        label: "Season",
        options: toOptions(
          [...new Set(all.map((row) => row.season))].sort((a, b) => b - a).map(String)
        ),
        valuesOf: (row) => [String(row.season)]
      }
    ];
  }, [data.topWeeks, data.topSeasons]);

  const filter = useFacetFilter<PlayerBoardRow>({
    rows: data.topSeasons,
    facets,
    sorts: [],
    searchText: playerSearchText
  });

  const weeks = useMemo(
    () =>
      filterRows(data.topWeeks, facets, filter.selected, filter.search, playerSearchText).filter(
        (row): row is PlayerWeekRow => "week" in row
      ),
    [data.topWeeks, facets, filter.selected, filter.search]
  );
  const seasons = filter.filtered.filter((row): row is PlayerSeasonRow => "weeks" in row);

  return (
    <section className="product-stack">
      <LeagueNav leagueId={leagueId} />
      <ProductHeader eyebrow="Players" title="Player leaderboards" />
      <p className="muted-note">
        Points reflect what each player scored while in a starting lineup. Bench weeks are excluded,
        so totals credit the manager who actually started them.
      </p>
      <FilterBar
        controller={filter}
        facets={facets}
        searchPlaceholder="Search players…"
        sorts={[]}
        total={data.topSeasons.length}
      />
      <TopWeeks directory={data.playerDirectory} rows={weeks} />
      <TopSeasons directory={data.playerDirectory} rows={seasons} />
      <EfficiencyBoard rows={data.lineupEfficiency} />
    </section>
  );
}

function TopWeeks({
  rows,
  directory
}: {
  readonly rows: readonly PlayerWeekRow[];
  readonly directory: PlayerDirectory;
}) {
  if (rows.length === 0) {
    return null;
  }
  return (
    <article className="product-panel">
      <p className="section-kicker">Top single-week performances</p>
      <ol className="player-board">
        {rows.map((row, index) => {
          const player = resolvePlayer(row, directory);
          return (
            <li
              key={`${row.playerName}-${row.season}-${row.week}`}
              className={`player-board__row${index === 0 ? " player-board__row--top" : ""}`}
            >
              <BoardRank index={index} />
              <PlayerChip
                playerId={player.playerId}
                name={row.playerName}
                teamAbbr={player.teamAbbr}
                position={player.position || row.position}
                isDST={player.isDST}
                badge={player.badge}
              />
              <span className="player-board__meta">
                {row.season} · Week {row.week} · {row.displayName}
              </span>
              <span className="player-board__points">{row.points.toFixed(1)}</span>
            </li>
          );
        })}
      </ol>
    </article>
  );
}

function TopSeasons({
  rows,
  directory
}: {
  readonly rows: readonly PlayerSeasonRow[];
  readonly directory: PlayerDirectory;
}) {
  if (rows.length === 0) {
    return null;
  }
  return (
    <article className="product-panel">
      <p className="section-kicker">Top player-seasons</p>
      <ol className="player-board">
        {rows.map((row, index) => {
          const player = resolvePlayer(row, directory);
          return (
            <li
              key={`${row.playerName}-${row.season}`}
              className={`player-board__row${index === 0 ? " player-board__row--top" : ""}`}
            >
              <BoardRank index={index} />
              <PlayerChip
                playerId={player.playerId}
                name={row.playerName}
                teamAbbr={player.teamAbbr}
                position={player.position || row.position}
                isDST={player.isDST}
                badge={player.badge}
              />
              <span className="player-board__meta">
                {row.season} · {row.displayName} · {row.weeks} starts
              </span>
              <span className="player-board__points">{row.points.toFixed(1)}</span>
            </li>
          );
        })}
      </ol>
    </article>
  );
}

function EfficiencyBoard({ rows }: { readonly rows: readonly LineupEfficiencyRow[] }) {
  if (rows.length === 0) {
    return null;
  }
  const ranked = [...rows]
    .sort((a, b) => b.aggregateEfficiency - a.aggregateEfficiency)
    .slice(0, 15);
  return (
    <article className="product-panel">
      <p className="section-kicker">Lineup-efficiency leaders</p>
      <p className="muted-note">
        Started points as a share of the optimal lineup — who left the least on their bench.
      </p>
      <ul className="efficiency-board">
        <li className="efficiency-row efficiency-row--head">
          <span>Manager</span>
          <span>Season</span>
          <span>Efficiency</span>
          <span>Bench pts</span>
        </li>
        {ranked.map((row) => (
          <li key={`${row.managerKey ?? row.displayName}-${row.season}`} className="efficiency-row">
            <span className="efficiency-row__name">{row.displayName}</span>
            <span>{row.season}</span>
            <span className="efficiency-row__pct">{row.aggregateEfficiency.toFixed(1)}%</span>
            <span>{row.benchPoints.toFixed(0)}</span>
          </li>
        ))}
      </ul>
    </article>
  );
}
