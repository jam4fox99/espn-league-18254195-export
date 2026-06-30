"use client";

import Link from "next/link";
import { useCallback } from "react";
import { useManagerLogo } from "@/components/manager-logos-provider";
import { LeagueNav, ProductHeader } from "@/components/product-chrome";
import { ProductLoader } from "@/components/product-loader";
import { StatusPill } from "@/components/status-pill";
import { TeamEmblem } from "@/components/team-emblem";
import type { LeagueHistoryData } from "@/lib/product-api";
import { readHistory } from "@/lib/product-api";
import type { AlphaSession } from "@/lib/session";

export function SeasonsIndex({ leagueId }: { readonly leagueId: string }) {
  const load = useCallback((session: AlphaSession) => readHistory(session, leagueId), [leagueId]);

  return (
    <ProductLoader load={load}>
      {(history) => (
        <section className="product-stack">
          <LeagueNav leagueId={leagueId} />
          <ProductHeader eyebrow="Seasons" title="Every season" />
          <div className="season-grid">
            {history.seasons.map((season) => (
              <SeasonTile key={season.season} leagueId={leagueId} season={season} />
            ))}
          </div>
        </section>
      )}
    </ProductLoader>
  );
}

function SeasonTile({
  leagueId,
  season
}: {
  readonly leagueId: string;
  readonly season: LeagueHistoryData["seasons"][number];
}) {
  const logoFor = useManagerLogo();
  const champ = season.champion;
  return (
    <Link className="season-tile" href={`/leagues/${leagueId}/seasons/${season.season}`}>
      <span className="season-tile__year">{season.season}</span>
      {season.isPartial ? (
        <StatusPill tone="info">In progress</StatusPill>
      ) : (
        <span className="season-tile__champ">
          {champ?.displayName ? (
            <TeamEmblem
              logo={logoFor(champ.managerKey, season.season)}
              name={champ.teamName ?? champ.displayName}
              size={26}
              you
            />
          ) : null}
          <span className="season-tile__champ-name">{champ?.displayName ?? "—"}</span>
        </span>
      )}
    </Link>
  );
}
