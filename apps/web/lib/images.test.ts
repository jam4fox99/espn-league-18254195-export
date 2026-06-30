import { describe, expect, it } from "vitest";
import {
  archetypeColor,
  attrColor,
  headshotUrl,
  isDstId,
  medalColor,
  monogram,
  ordinal,
  ovrTier,
  playerBadgeStyle,
  positionColor,
  recordTone,
  selectLogo,
  teamLogoUrl
} from "./images";

describe("image url builders", () => {
  it("builds the ESPN headshot url from a playerId", () => {
    expect(headshotUrl(3918298)).toBe(
      "https://a.espncdn.com/i/headshots/nfl/players/full/3918298.png"
    );
  });

  it("builds an NFL team logo url for D/ST, lowercased", () => {
    expect(teamLogoUrl("DET")).toBe("https://a.espncdn.com/i/teamlogos/nfl/500/det.png");
  });

  it("treats negative ids as D/ST", () => {
    expect(isDstId(-16034)).toBe(true);
    expect(isDstId(4430878)).toBe(false);
    expect(isDstId(null)).toBe(false);
    expect(isDstId(undefined)).toBe(false);
  });
});

describe("monogram", () => {
  it("takes initials from first + last name", () => {
    expect(monogram("Jake Milken")).toBe("JM");
  });
  it("falls back to two letters of a single token", () => {
    expect(monogram("Doug")).toBe("DO");
  });
  it("handles empty/missing names", () => {
    expect(monogram("")).toBe("?");
    expect(monogram(undefined)).toBe("?");
  });
});

describe("ovrTier", () => {
  it("maps ranges to the 3-tier scale ELITE/HIGH/AVERAGE", () => {
    expect(ovrTier(72).name).toBe("ELITE");
    expect(ovrTier(60).name).toBe("ELITE");
    expect(ovrTier(55).name).toBe("HIGH");
    expect(ovrTier(50).name).toBe("HIGH");
    expect(ovrTier(49).name).toBe("AVERAGE");
    expect(ovrTier(45).name).toBe("AVERAGE");
    expect(ovrTier(20).name).toBe("AVERAGE");
  });

  it("colors each tier from its token", () => {
    expect(ovrTier(72).color).toBe("var(--tier-elite)");
    expect(ovrTier(55).color).toBe("var(--tier-high)");
    expect(ovrTier(20).color).toBe("var(--tier-average)");
  });
});

describe("attrColor", () => {
  it("returns 3-tier colors by threshold (no separate low tier)", () => {
    expect(attrColor(80)).toBe("var(--tier-elite)");
    expect(attrColor(70)).toBe("var(--tier-elite)");
    expect(attrColor(60)).toBe("var(--tier-high)");
    expect(attrColor(45)).toBe("var(--tier-high)");
    expect(attrColor(44)).toBe("var(--tier-average)");
    expect(attrColor(10)).toBe("var(--tier-average)");
  });
});

describe("selectLogo — per-season vs main", () => {
  const logo = {
    main: "https://example.com/main-2026.png",
    mainSeason: 2026,
    bySeason: {
      "2020": "https://example.com/2020.png",
      "2026": "https://example.com/main-2026.png"
    }
  };

  it("returns that season's logo when a season is passed and present", () => {
    expect(selectLogo(logo, 2020)).toBe("https://example.com/2020.png");
  });

  it("returns the main logo for career/manager scope (no season)", () => {
    expect(selectLogo(logo)).toBe("https://example.com/main-2026.png");
  });

  it("falls back to main when the season key is missing", () => {
    expect(selectLogo(logo, 2099)).toBe("https://example.com/main-2026.png");
  });

  it("returns null for a missing logo bundle (→ monogram)", () => {
    expect(selectLogo(null)).toBeNull();
    expect(selectLogo(undefined, 2021)).toBeNull();
  });
});

describe("positionColor", () => {
  it("maps fantasy positions to distinct accents", () => {
    expect(positionColor("QB")).toBe("var(--magenta)");
    expect(positionColor("RB")).toBe("var(--tier-elite)");
    expect(positionColor("WR")).toBe("var(--blue)");
    expect(positionColor("TE")).toBe("var(--orange)");
    expect(positionColor("D/ST")).toBe("var(--indigo)");
  });
  it("falls back to steel for unknown/empty", () => {
    expect(positionColor("")).toBe("var(--steel)");
    expect(positionColor(undefined)).toBe("var(--steel)");
    expect(positionColor("FLEX")).toBe("var(--steel)");
  });
});

describe("playerBadgeStyle", () => {
  it("returns a short label, color, and blurb for known badges", () => {
    const screen = playerBadgeStyle("Screen Merchant");
    expect(screen?.short).toBe("SCREEN");
    expect(screen?.color).toBe("var(--tier-low)");
    expect(screen?.blurb).toContain("catches");
    expect(playerBadgeStyle("Boom or Bust")?.short).toBe("BOOM");
    expect(playerBadgeStyle("Injury Risk")?.color).toBe("var(--status-error)");
  });
  it("returns null for missing or unknown badges", () => {
    expect(playerBadgeStyle(null)).toBeNull();
    expect(playerBadgeStyle(undefined)).toBeNull();
    expect(playerBadgeStyle("")).toBeNull();
    expect(playerBadgeStyle("Not A Badge")).toBeNull();
  });
  it("styles every badge the worker can emit (must match player_badges.py BADGES)", () => {
    // Contract guard: if the worker renames/adds a badge, this list and the style
    // map must move together, or the pill silently disappears for that badge.
    const WORKER_BADGES = [
      "Elite Consistent",
      "High Floor",
      "Boom or Bust",
      "Explosive",
      "TD Dependent",
      "Screen Merchant",
      "Matchup Based",
      "Injury Risk"
    ];
    for (const badge of WORKER_BADGES) {
      const style = playerBadgeStyle(badge);
      expect(style, `missing style for "${badge}"`).not.toBeNull();
      expect(style?.short.length).toBeGreaterThan(0);
      expect(style?.color).toMatch(/^var\(--/);
    }
  });
});

describe("medalColor", () => {
  it("gives gold/silver/bronze for the top three, null otherwise", () => {
    expect(medalColor(1)).toBe("var(--yellow)");
    expect(medalColor(2)).toBe("#cbd5e6");
    expect(medalColor(3)).toBe("#e0934a");
    expect(medalColor(4)).toBeNull();
  });
});

describe("recordTone", () => {
  it("greens positives and reds negatives by default", () => {
    expect(recordTone(461.4)).toBe("var(--tier-elite)");
    expect(recordTone(-461.4)).toBe("var(--status-error)");
    expect(recordTone(0)).toBe("var(--text-primary)");
  });
  it("honors an explicit polarity over the raw sign", () => {
    expect(recordTone(461.4, "worst")).toBe("var(--status-error)");
    expect(recordTone(-153, "best")).toBe("var(--tier-elite)");
  });
});

describe("archetypeColor", () => {
  it("gives each archetype a distinct hue and is case-insensitive", () => {
    expect(archetypeColor("The Gambler")).toBe("var(--status-warning)");
    expect(archetypeColor("the analyst")).toBe("var(--blue)");
    expect(archetypeColor("The Opportunist")).toBe("var(--tier-elite)");
    expect(archetypeColor("The Aggressor")).toBe("var(--status-error)");
    expect(archetypeColor("The Lucky One")).toBe("var(--tier-high)");
  });
  it("falls back to steel for The Stoic and unknown labels", () => {
    expect(archetypeColor("The Stoic")).toBe("var(--tier-low)");
    expect(archetypeColor(undefined)).toBe("var(--tier-low)");
    expect(archetypeColor("Mystery")).toBe("var(--tier-low)");
  });
});

describe("ordinal", () => {
  it("formats ordinals", () => {
    expect(ordinal(1)).toBe("1st");
    expect(ordinal(2)).toBe("2nd");
    expect(ordinal(3)).toBe("3rd");
    expect(ordinal(11)).toBe("11th");
    expect(ordinal(21)).toBe("21st");
  });
});
