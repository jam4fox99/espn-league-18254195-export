"use client";

import { TeamEmblem } from "@/components/team-emblem";

type AliasItem = {
  readonly season?: number | undefined;
  readonly teamId?: string | number | undefined;
  readonly teamName?: string | undefined;
};

/**
 * Responsive grid of per-season identity cards (logo + team name + year) — replaces
 * the cramped comma-separated alias string. `logoOf` resolves the season's logo URL,
 * so each call site can feed it from `selectLogo` or the manager-logo provider.
 */
export function AliasGrid({
  aliases,
  logoOf
}: {
  readonly aliases: readonly AliasItem[];
  readonly logoOf: (season: number | undefined) => string | null | undefined;
}) {
  if (aliases.length === 0) {
    return null;
  }
  const ordered = [...aliases].sort((left, right) => (left.season ?? 0) - (right.season ?? 0));
  return (
    <div className="alias-grid">
      {ordered.map((alias) => {
        const team = alias.teamName ?? `Team ${alias.teamId ?? "?"}`;
        return (
          <article
            className="alias-card"
            key={`${alias.season ?? "season"}-${alias.teamId ?? alias.teamName ?? "team"}`}
          >
            <TeamEmblem logo={logoOf(alias.season) ?? null} name={team} size={34} />
            <span className="alias-card__team">{team}</span>
            <span className="alias-card__year">{alias.season ?? "—"}</span>
          </article>
        );
      })}
    </div>
  );
}
