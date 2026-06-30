# MyGM Design System — "2K / MyGM-Menu"

The MyGM web app wears a sports-video-game front-office skin: angular, glassy,
high-energy, but evidence-first underneath. The canonical reference is
`new-ui-test/mygm-menu.html`. This document is the source of truth for the
visual language; it supersedes the previous "RotoBot" cyan theme.

## 1. Principles

1. **Showcase loud, tools calm.** Loud flourishes (OVR rings, segmented meters,
   the row→hero promote, marquee, ambient gradient wash) live on the showcase
   surfaces. Utility surfaces (connect, import, login, admin, settings, data
   health, formula) share the same tokens and type but drop the arcade ornament.
   The credential form is **never** styled like a game.
2. **Never fabricate a number.** Withheld / ineligible / unresolved ratings
   render an explicit **`UNRATED`** plate (dimmed ring, reason on hover) — never
   a replacement numeral. Caveats are collapsed on showcase, fully exposed on
   data-health / formula / caveat drawers.
3. **No broken images, ever.** Every logo and headshot has a fallback: dead/
   missing logo → monogram initials; headshot 404/unknown → silhouette; D/ST
   (negative id) → NFL team logo. Dimensions are reserved (no layout shift).
4. **Motion is a guarantee, not a requirement.** All animation is
   `prefers-reduced-motion` gated and resolves to its final state instantly when
   reduced. Transform/opacity only; 60fps.

## 2. Tokens (`app/globals.css`)

Token **names** are unchanged from the legacy theme (so component CSS keeps
working); only their **values** changed, plus a few additions.

**Background.** Deep navy base `#0A0E1A → #0E1428`; a fixed diagonal gradient
wash (electric-blue `#1B6CF0` → indigo `#5B2BD9` → magenta `#E0249A`) on
`body::before`; thin angular slashes + scanlines on `body::after`; a darker
radial center keeps text readable.

**Accents.** Primary = electric **yellow `#FFE600`** (`--accent-primary`,
selected bars, active tab spine, key CTAs) with near-black `--ink #0A0E1A` text
on fills. Secondary: blue `#2E7BFF`, magenta `#E0249A`, green `#39D353`,
orange `#FF9A3C`, steel `#9AA7B8`.

**Surfaces / panels.** `--panel: rgba(18,26,43,.82)` with `backdrop-blur`, a 1px
`rgba(255,255,255,.08)` border, and **sharp/angular** corners (beveled via
`clip-path`, radii dropped to 4–6px). No soft rounded cards.

**Tier colors** (`--tier-*`): ELITE green `#39D353`, HIGH yellow `#FFE600`,
MID orange `#FF9A3C`, LOW steel `#9AA7B8`.

**Type.**
- `--font-display` = **Saira Condensed** (Oswald/Arial Narrow fallback) — names,
  headers, `OVR`, tab labels. Condensed bold UPPERCASE.
- `--font-app` = **Rubik** — body sans.
- `--font-tech` = **Chakra Petch** — kicker labels, stat chips.
- `--font-num` = JetBrains Mono — tabular stat numerals.
- Fonts load via `next/font/google` (layout.tsx) with system fallbacks.

## 3. Signature components

- **OVR ring** (`OvrRing`, `rating-visuals.tsx`): circular SVG, arc swept to the
  value, number centered with a small `OVR` label, colored by tier. Withheld →
  dimmed ring + `UNRATED` (no numeral).
- **Segmented meter** (`SegmentedMeter`): ~10 skewed discrete cells filled in
  tier color. Hero meters stagger-fill; dense row micro-meters fill at once.
  Component map: `OVR←score`, `RECORD & PTS←recordAndPoints`,
  `TRADE VALUE←tradeValue`, `WAIVER WIRE←waiverValue`, `LINEUP IQ←lineupEfficiency`.
- **Skewed tab-tiles** (`.league-nav` in `fantasy-theme.css`): angular
  parallelogram chips (`clip-path`) with a lit yellow spine on the active tab,
  plus a Tools▾ menu.
- **Hero + promote** (`GmRatingsBoard`): a #1 hero panel (big OVR ring,
  segmented meters, signature-player headshot, main-logo emblem, "View
  franchise" CTA). Clicking any ranking row promotes it into the hero.
- **TeamEmblem** (`team-emblem.tsx`): logo on a dark hexagonal plinth; monogram
  fallback. **PlayerImage / PlayerChip** (`player-image.tsx`): the headshot +
  `NAME` + `TEAM POS` chip (the Jahmyr Gibbs → "DET RB" layout) used everywhere
  a player is named.

## 4. Imagery (`next.config.ts` + the image layer)

- ESPN logos + headshots are remote via `next/image` + `remotePatterns`
  (`a.espncdn.com`, `g.espncdn.com`, `*.fantasy.espn.com`), CDN-cached/optimized.
- The ~20 rot-prone `CUSTOM_VALID` external league logos are baked into
  `public/logos/<season>/<ownerGuid>.<ext>` (`scripts/bake_logos.py`) and their
  snapshot URLs rewritten to local paths, so they can't rot.
- **Context-aware logos** (`selectLogo`): season-scoped surfaces pass the season
  → `logo.bySeason[season]`; career/manager surfaces use `logo.main` (the latest
  season the owner fielded a team); the Franchise Hub shows the full per-season
  logo-history strip.

## 5. Motion

- **One-shot (all showcase):** ring arc sweep, segmented cell fill, selection
  slide, row→hero promote, tab transition, hover glow — triggered on mount /
  scroll-into-view, once.
- **Ambient (landing + dashboard only):** slow animated gradient wash, the
  reigning-GM marquee, and the fun-facts ticker.
- All gated by `@media (prefers-reduced-motion: reduce)`.

## 6. Responsive

Breakpoints 375 / 768 / 1280 / 1536, no horizontal scroll anywhere. At 375 the
hero stacks, the OVR ring scales down, segmented meters wrap, dense tables expose
priority columns, and the `PlayerChip` collapses to headshot + name (team/pos in
the drawer). The share card is mobile-first.

## 7. CSS file map

- `globals.css` — tokens, fonts, background layers, reduced-motion guard.
- `app-shell.css` — topbar / page shell.
- `fantasy-theme.css` — leaderboard/standings/era chips + the 2K shell overrides
  (skewed tab nav, condensed headers, angular glass panels). Imported last.
- `product-surfaces.css` — the 2K primitives (emblem, player image/chip, OVR
  ring, segmented meter) + the GM hero/rows + history hero/marquee.
- `styles.css` — auth / connect / forms (calm tier).
