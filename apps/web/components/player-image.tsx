"use client";

import Image from "next/image";
import { useState } from "react";
import { headshotUrl, isDstId, playerBadgeStyle, positionColor, teamLogoUrl } from "../lib/images";

interface PlayerImageProps {
  readonly playerId?: number | null | undefined;
  readonly name: string;
  /** NFL team abbrev — required to render a D/ST team logo. */
  readonly teamAbbr?: string | null | undefined;
  /** Force the D/ST (team-logo) treatment regardless of id sign. */
  readonly isDST?: boolean | undefined;
  readonly size?: number | undefined;
  /** Hero headshots load eagerly; list chips lazy. */
  readonly priority?: boolean | undefined;
  readonly className?: string | undefined;
}

/** Inline silhouette — the universal "no headshot" fallback (§11). */
function Silhouette({ size, name }: { readonly size: number; readonly name: string }) {
  return (
    <svg
      className="player-image__silhouette"
      width={size}
      height={size}
      viewBox="0 0 40 40"
      role="img"
      aria-label={name}
    >
      <circle cx="20" cy="14" r="7.5" fill="currentColor" />
      <path d="M6 36c0-7.7 6.3-13 14-13s14 5.3 14 13z" fill="currentColor" />
    </svg>
  );
}

/**
 * A player's image: NFL headshot for real players, NFL team logo for D/ST
 * (negative id), silhouette on 404 / unknown / missing id. Headshots flow
 * through next/image (a.espncdn.com is in remotePatterns) for CDN optimization.
 */
export function PlayerImage({
  playerId,
  name,
  teamAbbr,
  isDST,
  size = 40,
  priority = false,
  className
}: PlayerImageProps) {
  const [failed, setFailed] = useState(false);
  const dst = isDST || isDstId(playerId);

  let src: string | null = null;
  if (dst) {
    src = teamAbbr ? teamLogoUrl(teamAbbr) : null;
  } else if (playerId != null) {
    src = headshotUrl(playerId);
  }

  const classes = ["player-image"];
  if (dst) {
    classes.push("player-image--dst");
  }
  if (className) {
    classes.push(className);
  }

  return (
    <span className={classes.join(" ")} style={{ width: size, height: size }}>
      {src && !failed ? (
        <Image
          src={src}
          alt={name}
          width={size}
          height={size}
          loading={priority ? "eager" : "lazy"}
          priority={priority}
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
          unoptimized={dst}
        />
      ) : (
        <Silhouette size={size} name={name} />
      )}
    </span>
  );
}

interface PlayerChipProps {
  readonly playerId?: number | null | undefined;
  readonly name: string;
  readonly teamAbbr?: string | null | undefined;
  readonly position?: string | null | undefined;
  readonly isDST?: boolean | undefined;
  readonly size?: number | undefined;
  /** Compact contexts hide the TEAM POS subtitle (revealed on hover/detail). */
  readonly compact?: boolean | undefined;
  /** Career signature badge name (e.g. "Screen Merchant"); renders a small pill. */
  readonly badge?: string | null | undefined;
  /** Trailing slot (e.g. points). */
  readonly trailing?: React.ReactNode | undefined;
  readonly className?: string | undefined;
}

/**
 * The "headshot + NAME + TEAM POS" chip used everywhere a player is named
 * (the Jahmyr Gibbs → "DET RB" layout). Falls back to name-only when there is
 * no id and no image. (§7d / §8 headshots)
 */
export function PlayerChip({
  playerId,
  name,
  teamAbbr,
  position,
  isDST,
  size = 34,
  compact = false,
  badge,
  trailing,
  className
}: PlayerChipProps) {
  const classes = ["player-chip-2k"];
  if (compact) {
    classes.push("player-chip-2k--compact");
  }
  if (className) {
    classes.push(className);
  }
  const badgeStyle = playerBadgeStyle(badge);

  return (
    <span className={classes.join(" ")}>
      <PlayerImage
        playerId={playerId}
        name={name}
        teamAbbr={teamAbbr}
        isDST={isDST}
        size={size}
        className="player-chip-2k__img"
      />
      <span className="player-chip-2k__id">
        <span className="player-chip-2k__name">
          <span className="player-chip-2k__name-text">{name}</span>
          {badgeStyle ? (
            <span
              className="player-chip-2k__badge"
              style={{ color: badgeStyle.color, borderColor: badgeStyle.color }}
              title={`${badge} — ${badgeStyle.blurb}`}
              role="img"
              aria-label={`Player badge: ${badge}. ${badgeStyle.blurb}`}
            >
              {badgeStyle.short}
            </span>
          ) : null}
        </span>
        {!compact && (teamAbbr || position) ? (
          <span className="player-chip-2k__sub">
            {teamAbbr ? <span className="player-chip-2k__team">{teamAbbr}</span> : null}
            {position ? (
              <span className="player-chip-2k__pos" style={{ color: positionColor(position) }}>
                {position}
              </span>
            ) : null}
          </span>
        ) : null}
      </span>
      {trailing ? <span className="player-chip-2k__trailing">{trailing}</span> : null}
    </span>
  );
}
