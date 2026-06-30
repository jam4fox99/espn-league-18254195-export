"use client";

/**
 * Shared design-system kit, extracted from the GM Leaderboard so every surface
 * renders the same primitives (next-build goal, Priority 1). These wrap the
 * existing 2K/MyGM CSS classes — the visual output is unchanged; the JSX is now
 * centralized and reusable.
 *
 *   TierBadge   — the Elite/High/Average (or UNRATED, or custom) pill
 *   StatBlock   — an attribute row: label + segmented meter + value (size prop)
 *   ManagerCard — the OVR-ring manager row (button or link variant)
 *
 * Already-reusable primitives live elsewhere and are re-exported for one import
 * site: OvrRing/SegmentedMeter (rating-visuals), TeamEmblem (team-emblem),
 * PlayerImage/PlayerChip (player-image).
 */

import type { Route } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import type { LeaderboardRow } from "@/components/leaderboard-rows";
import { PlayerImage } from "@/components/player-image";
import { OvrRing, SegmentedMeter } from "@/components/rating-visuals";
import { TeamEmblem } from "@/components/team-emblem";
import { archetypeColor, ovrTier, selectLogo } from "@/lib/images";

export { PlayerChip, PlayerImage } from "@/components/player-image";
export { OvrRing, SegmentedMeter } from "@/components/rating-visuals";
export { TeamEmblem } from "@/components/team-emblem";

/* ----------------------------------------------------------------- TierBadge */

type TierBadgeProps = {
  /** OVR score — when present (and not unrated), derives label + tier color. */
  readonly ovr?: number | null | undefined;
  /** Force the steel UNRATED pill regardless of `ovr`. */
  readonly unrated?: boolean | undefined;
  /** Explicit label override (e.g. a player badge name). Wins over `ovr`. */
  readonly label?: string | undefined;
  /** Explicit background color override (CSS color or var). Pairs with `label`. */
  readonly color?: string | undefined;
  /** `hero` = large pill (GM hero); `row` = compact pill (rows + inline badges). */
  readonly size?: "hero" | "row" | undefined;
  readonly title?: string | undefined;
  readonly className?: string | undefined;
};

/**
 * The Elite/High/Average pill. Renders the existing `.gm-hero__tier` /
 * `.gm-row__tier` look. Also accepts an explicit `label`+`color` so player
 * badges (Priority 2) share the exact same chip style.
 */
export function TierBadge({
  ovr,
  unrated,
  label,
  color,
  size = "row",
  title,
  className
}: TierBadgeProps) {
  let text: string;
  let background: string;
  if (label != null) {
    text = label;
    background = color ?? "var(--tier-average)";
  } else if (unrated || ovr == null || Number.isNaN(ovr)) {
    text = "UNRATED";
    background = "var(--tier-low)";
  } else {
    const tier = ovrTier(ovr);
    text = tier.name;
    background = tier.color;
  }
  const classes = [size === "hero" ? "gm-hero__tier" : "gm-row__tier", "tier-badge"];
  if (className) {
    classes.push(className);
  }
  return (
    <span className={classes.join(" ")} style={{ background }} title={title}>
      {text}
    </span>
  );
}

/* ----------------------------------------------------------------- StatBlock */

type StatBlockProps = {
  readonly label: string;
  /** 0–100 value: drives the segmented meter fill and the printed number. */
  readonly value: number | null | undefined;
  /** `hero` = large attribute row (.attr-2k); `micro` = dense row (.gm-row__micro). */
  readonly size?: "hero" | "micro" | undefined;
  /** Stagger the hero meter fill (showcase surfaces). */
  readonly stagger?: boolean | undefined;
};

/**
 * One attribute readout — label + segmented meter + value — at two sizes. Unifies
 * the hero `.attr-2k` and row `.gm-row__micro` variants behind a single component.
 */
export function StatBlock({ label, value, size = "hero", stagger = false }: StatBlockProps) {
  if (size === "micro") {
    return (
      <div className="gm-row__micro">
        <span className="gm-row__micro-k">{label}</span>
        <SegmentedMeter value={value} cells={10} mini />
        <span className="gm-row__micro-v">{value == null ? "—" : Math.round(value)}</span>
      </div>
    );
  }
  return (
    <div className="attr-2k">
      <span className="attr-2k__name">{label}</span>
      <SegmentedMeter value={value} cells={10} stagger={stagger} />
      <span className="attr-2k__val">{value == null ? "—" : value.toFixed(1)}</span>
    </div>
  );
}

/* --------------------------------------------------- Manager rating helpers */

export type RatingAttr = {
  readonly keys: readonly string[];
  /** Long label for the hero attribute list. */
  readonly label: string;
  /** Short label for compact rows. */
  readonly short: string;
};

/** The four GM-rating attributes, shared by every leaderboard surface. */
export const RATING_ATTRS: readonly RatingAttr[] = [
  { keys: ["recordandpoints", "record"], label: "RECORD & PTS", short: "RECORD" },
  { keys: ["tradevalue", "trade"], label: "TRADE VALUE", short: "TRADE" },
  { keys: ["waivervalue", "waiver"], label: "WAIVER WIRE", short: "WAIVER" },
  { keys: ["lineupefficiency", "lineup"], label: "LINEUP IQ", short: "LINEUP" }
];

/** Pull an attribute's 0–100 score out of a row's component breakdown. */
export function attrValue(row: LeaderboardRow, keys: readonly string[]): number | null {
  const entries = Object.entries(row.componentBreakdown ?? row.components ?? {});
  for (const [key, component] of entries) {
    const normalized = key.toLowerCase().replace(/[^a-z]/g, "");
    const label = (component.label ?? "").toLowerCase().replace(/[^a-z]/g, "");
    if (keys.some((k) => normalized.includes(k) || label.includes(k))) {
      return component.score ?? component.value ?? null;
    }
  }
  return null;
}

export function rowName(row: LeaderboardRow): string {
  return row.managerName ?? row.displayName ?? row.managerKey;
}

export function isWithheld(row: LeaderboardRow): boolean {
  return row.scoreEligible === false || row.score == null;
}

/* --------------------------------------------------------------- ManagerCard */

type ManagerCardProps = {
  readonly row: LeaderboardRow;
  /** Season scope for logo selection (career surfaces omit). */
  readonly season?: number | null | undefined;
  /** Optional trailing slot, e.g. an archetype badge or signature headshot. */
  readonly trailing?: ReactNode;
  /** Compact (preview) layout: drop the emblem + attribute micros for a narrow column. */
  readonly compact?: boolean | undefined;
} & (
  | { readonly href: string; readonly onSelect?: undefined; readonly selected?: undefined }
  | {
      readonly href?: undefined;
      readonly onSelect: (key: string) => void;
      readonly selected?: boolean | undefined;
    }
);

/**
 * The OVR-ring manager row (rank · ring · emblem · identity · attribute micros ·
 * trailing). Renders as a `<Link>` when given `href` (static leaderboards) or an
 * interactive `<button>` when given `onSelect` (the GM Ratings board hero pairing).
 */
export function ManagerCard({
  row,
  season,
  trailing,
  compact,
  href,
  onSelect,
  selected
}: ManagerCardProps) {
  const name = rowName(row);
  const withheld = isWithheld(row);
  const ovr = withheld ? null : (row.score ?? null);
  const sig = row.signaturePlayer;
  const base = compact ? "gm-row gm-row--compact" : "gm-row";

  const inner = (
    <div className="gm-row__inner">
      <div className="gm-row__rank">
        {row.rank ?? "—"}
        <small>RNK</small>
      </div>
      <OvrRing ovr={ovr} size={56} stroke={5} withheld={withheld} />
      <TeamEmblem
        className="gm-row__emblem"
        logo={selectLogo(row.logo, season)}
        name={name}
        size={44}
        you={row.you}
      />
      <div className="gm-row__id">
        <div className="gm-row__name">{name}</div>
        <div className="gm-row__sub">
          <TierBadge ovr={ovr} size="row" />
          {row.archetype?.name ? (
            <TierBadge
              label={row.archetype.name}
              color={archetypeColor(row.archetype.name)}
              size="row"
              className="gm-row__archetype"
              title={row.archetype.oneLiner}
            />
          ) : null}
          {row.teamName ? <span className="gm-row__team">{row.teamName}</span> : null}
        </div>
      </div>
      <div className="gm-row__micros">
        {RATING_ATTRS.map((attr) => (
          <StatBlock
            key={attr.short}
            label={attr.short}
            value={attrValue(row, attr.keys)}
            size="micro"
          />
        ))}
      </div>
      <div className="gm-row__stats">
        {trailing ??
          (sig ? <PlayerImage playerId={sig.playerId} name={sig.name} size={34} /> : null)}
      </div>
    </div>
  );

  if (href) {
    return (
      <Link className={`${base} gm-row--static${row.you ? " is-you" : ""}`} href={href as Route}>
        {inner}
      </Link>
    );
  }

  const classes = [base];
  if (selected) {
    classes.push("is-selected");
  }
  if (row.you) {
    classes.push("is-you");
  }
  return (
    <button
      type="button"
      className={classes.join(" ")}
      aria-pressed={selected}
      onClick={() => onSelect?.(row.managerKey)}
    >
      {inner}
    </button>
  );
}
