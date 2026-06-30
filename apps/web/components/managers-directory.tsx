"use client";

import Link from "next/link";
import { useCallback } from "react";
import { LeagueNav, ProductHeader } from "@/components/product-chrome";
import { ProductLoader } from "@/components/product-loader";
import { TeamEmblem } from "@/components/team-emblem";
import { selectLogo } from "@/lib/images";
import { readManagerDirectory } from "@/lib/product-api";
import { scoreLine } from "@/lib/product-model";
import type { AlphaSession } from "@/lib/session";

export function ManagersDirectory({ leagueId }: { readonly leagueId: string }) {
  const load = useCallback(
    (session: AlphaSession) => readManagerDirectory(session, leagueId),
    [leagueId]
  );

  return (
    <ProductLoader load={load}>
      {(directory) => (
        <section className="product-stack">
          <LeagueNav leagueId={leagueId} />
          <ProductHeader eyebrow="Managers" title="Franchise directory" />
          {directory.managers.length === 0 ? (
            <p className="muted-note">No managers are available for this snapshot.</p>
          ) : (
            <ol className="manager-directory">
              {directory.managers.map((manager, index) => (
                <li key={manager.managerKey} className="manager-card">
                  <span className="manager-card__rank">{index + 1}</span>
                  <TeamEmblem
                    logo={selectLogo(manager.logo)}
                    name={manager.latestTeamName ?? manager.displayName}
                    size={42}
                  />
                  <div className="manager-card__identity">
                    <Link
                      className="manager-card__name"
                      href={`/leagues/${leagueId}/managers/${encodeURIComponent(manager.managerKey)}`}
                    >
                      {manager.displayName}
                    </Link>
                    {manager.latestTeamName ? (
                      <span className="manager-card__team">{manager.latestTeamName}</span>
                    ) : null}
                  </div>
                  <span className="manager-card__stat">
                    {scoreLine(manager.careerRating ?? null)}
                    <small>GM rating</small>
                  </span>
                  <span className="manager-card__stat">
                    {manager.titles ?? 0}
                    <small>titles</small>
                  </span>
                  <span className="manager-card__stat">
                    {formatPct(manager.winPct)}
                    <small>win %</small>
                  </span>
                </li>
              ))}
            </ol>
          )}
        </section>
      )}
    </ProductLoader>
  );
}

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  return `${value.toFixed(1)}%`;
}
