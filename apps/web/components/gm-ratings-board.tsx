"use client";

import Link from "next/link";
import { useCallback, useMemo, useRef, useState } from "react";
import type { LeaderboardRow } from "@/components/leaderboard-rows";
import { PlayerImage } from "@/components/player-image";
import { OvrRing } from "@/components/rating-visuals";
import { TeamEmblem } from "@/components/team-emblem";
import {
  attrValue,
  isWithheld,
  ManagerCard,
  RATING_ATTRS,
  rowName,
  StatBlock,
  TierBadge
} from "@/components/ui-kit";
import { archetypeColor, selectLogo } from "@/lib/images";

export function GmRatingsBoard({
  leagueId,
  rows
}: {
  readonly leagueId: string;
  readonly rows: readonly LeaderboardRow[];
}) {
  const ordered = useMemo(() => rows.filter((row) => row.managerKey), [rows]);
  const [selectedKey, setSelectedKey] = useState<string | undefined>(ordered[0]?.managerKey);
  const heroRef = useRef<HTMLDivElement | null>(null);

  const selected = ordered.find((row) => row.managerKey === selectedKey) ?? ordered[0];

  const select = useCallback((key: string) => {
    setSelectedKey(key);
    requestAnimationFrame(() => {
      heroRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, []);

  if (ordered.length === 0 || !selected) {
    return <p className="muted-note">No leaderboard rows are available for this snapshot.</p>;
  }

  return (
    <div className="gm-board">
      <GmHero ref={heroRef} leagueId={leagueId} row={selected} />
      <ol className="gm-rows">
        {ordered.map((row) => (
          <li key={row.managerKey}>
            <ManagerCard
              row={row}
              selected={row.managerKey === selected.managerKey}
              onSelect={select}
            />
          </li>
        ))}
      </ol>
    </div>
  );
}

function GmHero({
  row,
  leagueId,
  ref
}: {
  readonly row: LeaderboardRow;
  readonly leagueId: string;
  readonly ref: React.Ref<HTMLDivElement>;
}) {
  const withheld = isWithheld(row);
  const ovr = withheld ? null : (row.score ?? null);
  const name = rowName(row);
  const rank = row.rank;
  const sig = row.signaturePlayer;
  const reason = (row.caveats ?? [])[0] ?? "Score withheld or ineligible";

  return (
    <div className="gm-hero" ref={ref}>
      <div className="gm-hero__tag">
        {rank === 1 ? "★ TOP RATED GM" : rank ? `#${rank} · GM RATING` : "GM RATING"}
      </div>
      <div className="gm-hero__grid">
        <div className="gm-hero__left">
          <OvrRing ovr={ovr} size={170} stroke={12} withheld={withheld} unratedReason={reason} />
          {withheld ? null : <TierBadge ovr={ovr} size="hero" />}
          <TeamEmblem logo={selectLogo(row.logo)} name={name} size={84} you={row.you} />
        </div>
        <div className="gm-hero__mid">
          <h2>{name}</h2>
          <div className="gm-hero__role">GENERAL MANAGER{rank ? ` · #${rank}` : ""}</div>
          {row.teamName ? <div className="gm-hero__team">&ldquo;{row.teamName}&rdquo;</div> : null}
          {row.archetype?.name ? (
            <div className="gm-hero__dna">
              <span
                className="gm-hero__dna-badge"
                style={{ background: archetypeColor(row.archetype.name) }}
              >
                {row.archetype.name}
              </span>
              {row.archetype.oneLiner ? (
                <span className="gm-hero__dna-line">{row.archetype.oneLiner}</span>
              ) : null}
            </div>
          ) : null}
          {sig ? (
            <div className="gm-hero__sig">
              <PlayerImage playerId={sig.playerId} name={sig.name} size={54} priority />
              <span className="gm-hero__sig-meta">
                <span className="gm-hero__sig-k">Signature player</span>
                <span className="gm-hero__sig-name">{sig.name}</span>
                <span className="gm-hero__sig-sub">
                  {sig.season ? `${sig.season} · ` : ""}
                  {sig.points != null ? `${sig.points.toFixed(1)} pts` : ""}
                </span>
              </span>
            </div>
          ) : null}
          <Link
            className="gm-hero__cta"
            href={`/leagues/${leagueId}/gms/${encodeURIComponent(row.managerKey)}`}
          >
            Full breakdown →
          </Link>
        </div>
        <div className="gm-hero__right">
          <div className="gm-hero__attr-title">Attributes</div>
          {RATING_ATTRS.map((attr) => (
            <StatBlock
              key={attr.label}
              label={attr.label}
              value={attrValue(row, attr.keys)}
              size="hero"
              stagger
            />
          ))}
        </div>
      </div>
    </div>
  );
}
