/**
 * Image + identity helpers for the 2K / MyGM-Menu UI.
 *
 * Pure, framework-free, and unit-tested. URL templates follow
 * docs/2k-ui-port-goal.md §7b. Logos that are league-uploaded and rot-prone
 * are baked to local /logos paths by scripts/bake_logos.py; everything here
 * just builds the canonical remote URLs and the fallback primitives.
 */

/** ESPN NFL headshot for a (positive) playerId. next/image optimizes it. */
export function headshotUrl(playerId: number | string): string {
  return `https://a.espncdn.com/i/headshots/nfl/players/full/${playerId}.png`;
}

/** NFL team logo, used for D/ST (negative playerId) in place of a headshot. */
export function teamLogoUrl(abbr: string): string {
  return `https://a.espncdn.com/i/teamlogos/nfl/500/${abbr.toLowerCase()}.png`;
}

/** A negative playerId denotes an ESPN D/ST "player". */
export function isDstId(playerId: number | string | null | undefined): boolean {
  if (playerId === null || playerId === undefined) {
    return false;
  }
  return Number(playerId) < 0;
}

/** Two-letter monogram from a team or manager name (dead/missing logo fallback). */
export function monogram(name: string | null | undefined): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) {
    return "?";
  }
  const first = parts[0]?.[0] ?? "";
  const second = parts[1]?.[0] ?? parts[0]?.[1] ?? "";
  return (first + second).toUpperCase();
}

export type OvrTier = "ELITE" | "HIGH" | "AVERAGE";

export interface TierInfo {
  readonly name: OvrTier;
  readonly color: string;
}

/**
 * The single tunable source of truth for the 3-tier system (Elite / High /
 * Average). Collapsed from the legacy 4-tier scale: the old MID + LOW bands
 * merge into AVERAGE — there is no separate Low/Bust tier (next-build goal,
 * Priority 1). The steel `--tier-low` token is retained ONLY for the distinct
 * UNRATED/withheld state, which is not a tier.
 *
 *   OVR ≥ elite  → ELITE   (green)
 *   OVR ≥ high   → HIGH    (gold)
 *   else         → AVERAGE (amber floor)
 *
 * Attribute meters use a separate (wider) band on the same 0–100 scale.
 */
export const OVR_TIER_THRESHOLDS = { elite: 60, high: 50 } as const;
export const ATTR_TIER_THRESHOLDS = { elite: 70, high: 45 } as const;

/** OVR → tier + tier color (3-tier system). */
export function ovrTier(ovr: number): TierInfo {
  if (ovr >= OVR_TIER_THRESHOLDS.elite) {
    return { name: "ELITE", color: "var(--tier-elite)" };
  }
  if (ovr >= OVR_TIER_THRESHOLDS.high) {
    return { name: "HIGH", color: "var(--tier-high)" };
  }
  return { name: "AVERAGE", color: "var(--tier-average)" };
}

/** Attribute-meter value → fill color (segmented meters, 3-tier system). */
export function attrColor(value: number): string {
  if (value >= ATTR_TIER_THRESHOLDS.elite) {
    return "var(--tier-elite)";
  }
  if (value >= ATTR_TIER_THRESHOLDS.high) {
    return "var(--tier-high)";
  }
  return "var(--tier-average)";
}

/**
 * Fantasy-position → accent color (Players leaderboard + every PlayerChip).
 * One tunable place; unknown/empty positions fall back to neutral steel.
 */
export function positionColor(position: string | null | undefined): string {
  switch ((position ?? "").toUpperCase().replace(/[^A-Z/]/g, "")) {
    case "QB":
      return "var(--magenta)";
    case "RB":
      return "var(--tier-elite)";
    case "WR":
      return "var(--blue)";
    case "TE":
      return "var(--orange)";
    case "K":
      return "var(--yellow)";
    case "D/ST":
    case "DST":
      return "var(--indigo)";
    default:
      return "var(--steel)";
  }
}

/** Medal color for a 1-indexed rank (1=gold, 2=silver, 3=bronze, else null). */
export function medalColor(rank: number): string | null {
  if (rank === 1) {
    return "var(--yellow)";
  }
  if (rank === 2) {
    return "#cbd5e6";
  }
  if (rank === 3) {
    return "#e0934a";
  }
  return null;
}

/**
 * Record-book value tone: positive/"best" marks read green, negative/"worst"
 * marks read red, everything else stays neutral. `polarity` lets a record whose
 * raw number is positive still be flagged as a "worst" (e.g. worst trade).
 */
export function recordTone(
  value: number | string,
  polarity: "best" | "worst" | "neutral" = "neutral"
): string {
  if (polarity === "best") {
    return "var(--tier-elite)";
  }
  if (polarity === "worst") {
    return "var(--status-error)";
  }
  const numeric = typeof value === "number" ? value : Number.parseFloat(value);
  if (Number.isFinite(numeric)) {
    if (numeric > 0) {
      return "var(--tier-elite)";
    }
    if (numeric < 0) {
      return "var(--status-error)";
    }
  }
  return "var(--text-primary)";
}

/** Brand color for a manager archetype ("GM DNA") pill — one hue per archetype. */
export function archetypeColor(name: string | null | undefined): string {
  switch ((name ?? "").trim().toLowerCase()) {
    case "the gambler":
      return "var(--status-warning)";
    case "the analyst":
      return "var(--blue)";
    case "the opportunist":
      return "var(--tier-elite)";
    case "the aggressor":
      return "var(--status-error)";
    case "the lucky one":
      return "var(--tier-high)";
    default:
      // The Stoic + any unknown future archetype read as calm steel.
      return "var(--tier-low)";
  }
}

/** Compact label + color + tooltip for a career player badge (see worker player_badges.py). */
export interface PlayerBadgeStyle {
  readonly short: string;
  readonly color: string;
  readonly blurb: string;
}

const PLAYER_BADGE_STYLES: Record<string, PlayerBadgeStyle> = {
  "Elite Consistent": {
    short: "ELITE",
    color: "var(--tier-elite)",
    blurb: "Elite weekly scorer who almost never busts."
  },
  "High Floor": {
    short: "FLOOR",
    color: "var(--blue)",
    blurb: "Dependable points every week — a safe, steady starter."
  },
  "Boom or Bust": {
    short: "BOOM",
    color: "var(--status-warning)",
    blurb: "League-winner ceiling, season-killer floor — wild week to week."
  },
  Explosive: {
    short: "EXPLO",
    color: "var(--tier-high)",
    blurb: "Big-play threat who turns touches into chunk yardage."
  },
  "TD Dependent": {
    short: "TD",
    color: "var(--badge-td)",
    blurb: "Lives and dies by the end zone — value rides on touchdowns."
  },
  "Screen Merchant": {
    short: "SCREEN",
    color: "var(--tier-low)",
    blurb: "High-volume short-area target; lots of catches, few yards each."
  },
  "Matchup Based": {
    short: "MATCH",
    color: "var(--badge-matchup)",
    blurb: "Feasts on weak defenses, disappears against strong ones."
  },
  "Injury Risk": {
    short: "INJ",
    color: "var(--status-error)",
    blurb: "Frequently on the injury report — availability is the question."
  }
};

export function playerBadgeStyle(badge: string | null | undefined): PlayerBadgeStyle | null {
  if (!badge) {
    return null;
  }
  return PLAYER_BADGE_STYLES[badge] ?? null;
}

export function ordinal(n: number): string {
  const suffixes = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return `${n}${suffixes[(v - 20) % 10] ?? suffixes[v] ?? suffixes[0]}`;
}

/** One entry in the snapshot's player dimension table (§6b). */
export interface PlayerDirectoryEntry {
  readonly playerId: number;
  readonly name: string;
  readonly position: string;
  readonly proTeamAbbrev: string;
  readonly latestSeason: number;
  readonly isDST: boolean;
}

export type PlayerDirectory = Record<string, PlayerDirectoryEntry>;

/** A logo bundle as emitted per manager (§6a). */
export interface ManagerLogo {
  readonly main?: string | null | undefined;
  readonly mainSeason?: number | null | undefined;
  readonly bySeason?: Record<string, string> | undefined;
}

/**
 * Context-aware logo selection (§7e): a season-scoped surface passes that
 * season and gets that season's logo; career/manager surfaces pass no season
 * and get `main`. Missing season key → fall back to `main` → null (monogram).
 */
export function selectLogo(
  logo: ManagerLogo | null | undefined,
  season?: number | null
): string | null {
  if (!logo) {
    return null;
  }
  if (season != null) {
    const exact = logo.bySeason?.[String(season)];
    if (exact) {
      return exact;
    }
  }
  return logo.main ?? null;
}
