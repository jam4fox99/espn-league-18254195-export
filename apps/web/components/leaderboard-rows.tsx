"use client";

import { ManagerCard } from "@/components/ui-kit";
import type { ManagerLogo } from "@/lib/images";
import type { Archetype, SignaturePlayer } from "@/lib/product-api";

type ScoreComponent = {
  readonly label?: string | undefined;
  readonly value?: number | null | undefined;
  readonly score?: number | null | undefined;
  readonly weight?: number | undefined;
  readonly caveats?: readonly string[] | undefined;
};

export type LeaderboardRow = {
  readonly managerKey: string;
  readonly rank?: number | undefined;
  readonly managerName?: string | undefined;
  readonly displayName?: string | undefined;
  readonly teamName?: string | undefined;
  readonly score?: number | null | undefined;
  readonly scoreEligible?: boolean | undefined;
  readonly confidence?: string | undefined;
  readonly caveats?: readonly string[] | undefined;
  readonly componentBreakdown?: Record<string, ScoreComponent> | undefined;
  readonly components?: Record<string, ScoreComponent> | undefined;
  readonly logo?: ManagerLogo | null | undefined;
  readonly signaturePlayer?: SignaturePlayer | null | undefined;
  readonly archetype?: Archetype | null | undefined;
  readonly you?: boolean | undefined;
};

/**
 * Compact all-time leaderboard as OVR-ring rows (dashboard preview). The full
 * hero+promote experience lives in GmRatingsBoard on the GM Ratings surface.
 * Each row is the shared {@link ManagerCard} in its static (link) form.
 */
export function LeaderboardRows({
  leagueId,
  rows,
  compact = false
}: {
  readonly leagueId: string;
  readonly rows: readonly LeaderboardRow[];
  /** Compact preview (e.g. the Home column) — drops the emblem + attribute micros. */
  readonly compact?: boolean;
}) {
  if (rows.length === 0) {
    return <p className="muted-note">No leaderboard rows are available for this snapshot.</p>;
  }
  return (
    <ol className="gm-rows gm-rows--static">
      {rows.map((row) => (
        <li key={row.managerKey}>
          <ManagerCard
            row={row}
            compact={compact}
            href={`/leagues/${leagueId}/gms/${encodeURIComponent(row.managerKey)}`}
          />
        </li>
      ))}
    </ol>
  );
}
