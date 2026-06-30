# Goal: Port MyGM to the "2K / MyGM-Menu" UI, wire team logos + player headshots everywhere, ship live

> **How to run:** paste this whole file into `/goal` (or hand it to a fresh agent). It is the
> single source of truth for the build. It supersedes `new-ui-test/docs/implementation-handoff.md`.
> Every decision below is **locked** — do not re-litigate; implement it.

---

## 0. One-line goal

Re-skin the entire MyGM web app to the **MyGM-Menu** sports-game look (from `new-ui-test/mygm-menu.html`),
**wire real ESPN team logos (per-season) and NFL player headshots into every surface**, keep the
evidence-first substance intact, and **deploy the demo league live to the existing Vercel projects** —
all in one pass, gated by a full proof checklist.

## 1. Current state (so you know what you're modifying)

- **App:** Next.js 16 App Router, React 19, token-based CSS (no Tailwind config), Zod-validated.
  Web talks to a FastAPI over HTTP (`ky`), base URL `NEXT_PUBLIC_API_BASE_URL`.
- **Live today:** web `https://mygm-espn-alpha.vercel.app`, API `https://mygm-api-alpha.vercel.app`.
  The Vercel API is an **alpha bridge serving a baked snapshot fixture** for the demo league
  `18254195`. **No durable worker / Supabase in prod** (Railway blocked) — and **we are not changing that**.
- **Theme today:** a dark "RotoBot" cyan theme in `apps/web/app/globals.css` (tokens `--surface-*`,
  `--accent-primary:#00d3f2`, grade scale, category accents). This is what we **replace**.
- **Historian build (this branch):** the IA and routes (History, Managers, Seasons, Rivalries,
  Record Book, Players, Franchise Hub, Season Hub, plus the tools) already exist. We re-skin them;
  we do not restructure the IA.
- **Images today:** none. No `<img>`, no `next/image`, no `remotePatterns`. We add all of it.
- **The mockup `DATA` already carries `logo` + `sig` fields** as a convenience — but images are NOT
  wired in the mockup. Wiring them for real is half of this goal.

## 2. Locked decisions (source of truth)

| # | Decision | Value |
|---|---|---|
| 1 | Canonical look | **MyGM-Menu**: angular skewed tab-tiles, a #1 **hero** panel, ranking as **OVR-ring** rows; clicking a row promotes it into the hero |
| 2 | Theme strategy | **Replace in place** — one theme. Retheme tokens + restyle components. **Rewrite `DESIGN.md`** to the new language. No theme toggle. |
| 3 | Surface scope | **Tiered.** Same skin everywhere; **loud** flourishes (rings, meters, marquee, big motion) on **showcase**; **calm** subset on **utility**; share card privacy-safe. |
| 4 | Evidence UX | **Clean showcase, receipts in tools.** No confidence chip on showcase; caveats collapsed; full confidence/withheld/provenance on data-health + formula + caveat drawer. **Withheld/ineligible → explicit `UNRATED` plate, never a fabricated number.** |
| 5 | Deploy scope | **Demo league live, no backend buildout.** Renders demo league `18254195` from the baked snapshot fixture. Keep all code **league-agnostic** (no hardcoded names/ids/counts in product logic). Do NOT stand up worker/Supabase/Railway. |
| 6 | Image caching | **Hybrid.** `next/image` + `remotePatterns` for ESPN hosts (CDN-cached/optimized). **Bake only the ~20 rot-prone `CUSTOM_VALID` external logos** into `apps/web/public/logos/` and rewrite those snapshot URLs to local paths. Wrapper components carry fallbacks. |
| 7 | Logo rule | **Context-aware.** Season-scoped surfaces → that season's logo; career/manager-scoped → **main = latest season the owner fielded a team**; Franchise Hub shows a per-season **logo-history strip**. Derive from raw `season_*/core.json` keyed by **owner GUID** (not the snapshot alias). Dead/missing → **monogram initials**. |
| 8 | Headshots | **Full "TEAM POS" chip everywhere a player is named** (matches the attached Jahmyr Gibbs → "DET RB" example). Build a **574-player worker dimension table** (playerId → name, position, NFL-team abbrev, headshot). Emit `playerId` on every player-bearing row; backfill leaderboards by (name, season). D/ST (neg id) → NFL team logo; unknown/404 → silhouette. |
| 9 | Motion | **Full one-shot + interaction motion on all showcase surfaces** (ring/meter fills on scroll-in, selection slide, row→hero promote, tab transitions, hover glow). **Ambient loops** (animated gradient wash, reigning-GM marquee, fun-facts ticker) **on landing/dashboard only.** All `prefers-reduced-motion` gated; transform/opacity only; 60fps. |
| 10 | Responsive | **Full responsive 375→1536** on every surface. No horizontal scroll anywhere. Share card mobile-first. |
| 11 | Deliverable/run | This file (`docs/2k-ui-port-goal.md`), pasted into `/goal`. |
| 12 | Acceptance | **Full proof gate** (§12). Nothing ships until all green. |

### Baked-in defaults (decided, lower-stakes)
- **Nav/IA:** keep the historian IA, rendered *as* 2K skewed tab-tiles + a Tools▾ menu. Do not invent IA.
- **GM-ratings interaction:** row click promotes into the in-page hero **and** the hero has a
  **"View franchise" CTA → `/leagues/[leagueId]/managers/[managerKey]`** (the Franchise Hub).
- **Type:** add **Saira Condensed** (display, for names/headers/`OVR`), keep a clean body sans
  (Rubik is fine) + tabular numerals for stats; Google Fonts via `<link>` with **system fallbacks**.
- **Markup/tests:** preserve semantic HTML and existing class names where possible so structural
  selectors survive; new DOM (rings/meters/hero/chips) is **additive**; update text/visual assertions.
- **Branch/deploy:** build on the current `historian-build` state; **one** live cutover at the end.

## 3. Scope

**Showcase (loud):** League History landing, Dashboard/Overview, GM Ratings, Manager/Franchise Hub,
Season Hub, Players, Record Book, Trades, Waivers, Rivalries, Head-to-head.

**Utility (calm — same tokens/type/panels, minimal motion, no arcade ornament):** Connect (ESPN
cookies), Import status, Login/Invite, Admin, Settings, Data Health, Formula.

**Privacy-safe, restyled:** Public share card (`/s/[shareSlug]`) + its OG image route.

**Non-goals:** durable worker/Supabase/Railway; live multi-league import; new analytics/metrics;
new IA; changing the GM rating math; ADP/draft grades; any fabricated score; ESPN/Sleeper/Yahoo scope creep.

## 4. Design system (the 2K language)

Define a new token layer in `apps/web/app/globals.css` (the existing `--surface-*`/`--text-*`/
`--accent-*`/`--grade-*` names stay — we change their **values** and add a few). All component CSS
already references tokens, so most surfaces re-skin by token swap + targeted component CSS.

**Background:** deep navy base `#0A0E1A → #0E1428`; diagonal gradient wash electric-blue `#1B6CF0` →
indigo `#5B2BD9` → magenta `#E0249A`; thin angular slashes + faint scanlines + subtle grain; darker
center for text readability (scrim behind text on busy areas).

**Primary accent = yellow `#FFE600`** (selected bars, active tab spine, key CTAs) with near-black
`#0A0E1A` text on fills. Secondary: blue `#2E7BFF`, magenta `#E0249A`, green `#39D353`.

**Panels:** glassy charcoal-navy `rgba(18,26,43,.82)`, `backdrop-blur`, 1px border
`rgba(255,255,255,.08)`, **sharp/angular** corners (beveled via `clip-path`). No soft rounded cards.

**OVR display:** circular SVG **ring**, number centered + small `OVR` label, arc swept to value,
colored by tier — **ELITE** green `#39D353`, **HIGH** yellow `#FFE600`, **MID** orange `#FF9A3C`,
**LOW** steel `#9AA7B8`. Withheld → dimmed ring + `UNRATED` (no numeral).

**Attribute meters:** **segmented** (~10 discrete cells) filled in accent/tier color. Map:
`OVR`←`score`; `RECORD & PTS`←`recordAndPoints`; `TRADE VALUE`←`tradeValue`; `WAIVER WIRE`←`waiverValue`;
`LINEUP IQ`←`lineupEfficiency`. (Use the v2 historian components.)

**Tabs:** angular parallelogram chips (`skewX(-12deg)` container, `skewX(12deg)` inner) with ◆
separators; active = lit/yellow spine.

**Type:** condensed bold UPPERCASE for names/headers (Saira Condensed), clean sans body, tabular nums.

**CSS files to touch:** `globals.css` (tokens, fonts, background), `app-shell.css` (topbar/nav/tabs),
`fantasy-theme.css` (leaderboard/standings/era chips), `product-surfaces.css` (panels/hero/metric
strip/record grid), `styles.css` (auth/connect/forms — calm tier).

## 5. Per-surface spec

> Pattern for every league page: `AppFrame → ClientOnly → AuthGate → <Component>`. Re-skin the
> component; keep the wrapper. Restyle targets cited with their files.

- **League History landing** (`league-history.tsx`, `/leagues/[id]`): loud. Hero of the reigning
  GM/champion; season timeline as ladder; **ambient gradient wash + reigning-GM marquee + fun-facts
  ticker live here (and dashboard) only.** Season logos on each season row.
- **Dashboard/Overview** (`league-dashboard.tsx`, `/overview`): loud. Metric strip → angular panels;
  all-time leaderboard preview as OVR-ring rows; ambient motion allowed.
- **GM Ratings** (`analytics-page.tsx` = GmRatingsPage + `leaderboard-rows.tsx`, `/gms`): loud,
  flagship. OVR-ring rows for all GMs; **row click → promote into in-page hero** (big OVR numeral +
  segmented meters + signature-player headshot hero + main logo emblem); hero CTA **"View franchise"**
  → `/managers/[managerKey]`. `you:true` (owner) highlighted. Withheld GMs render `UNRATED` plate.
- **Managers directory** (`managers-directory.tsx`, `/managers`): loud. Card grid; **main logo**
  emblem on a dark plinth; career line; click → Franchise Hub.
- **Franchise Hub** (`franchise-hub.tsx` + `franchise-charts.tsx`, `/managers/[managerKey]`): loud.
  Header emblem = **main logo**; **per-season logo-history strip** (`bySeason` 2020→latest); signature
  player hero; radar (rating components), franchise stock line, season timeline, trophy/eras, trade/
  waiver ledgers with **player headshot chips**, rivalry splits.
- **Season Hub** (`season-hub.tsx`, `/seasons/[year]`): loud. **All team logos = THAT season's logo.**
  Final standings, champion, draft recap (headshot chips per pick), all moves, Season-in-Review.
- **Players** (`players-page.tsx`, `/players`): loud. Top weeks / top seasons / efficiency boards —
  **headshot chip per row** (backfill `playerId`). Primary headshot surface.
- **Record Book** (`record-book.tsx`, `/record-book`): loud. Record cards by category; **headshot chip**
  on the holder where a record names a player; main/season logo on the manager.
- **Trades** (`trades-page.tsx` + `trades-page-parts.tsx`, `/trades`): loud, browse-first. Each side's
  assets render **headshot chips**; manager emblems; keep grades but de-emphasized; caveats in drawer.
- **Waivers** (`waivers-page.tsx` + `waivers-page-parts.tsx`, `/waivers`): loud. Added/dropped players
  as **headshot chips**; manager emblem; browsable history.
- **Rivalries** (`rivalries-matrix.tsx`, `/rivalries`): loud. Matrix heatmap; manager emblems (main).
- **Head-to-head** (`head-to-head-page.tsx`, `/head-to-head`): loud. Manager emblems; resolved names
  only (no raw `managerKey`).
- **Data Health** (`data-health-page.tsx`) + **Formula** (`formula-page.tsx`): **calm.** Full
  confidence/withheld/provenance lives here. Restyled, scannable, minimal motion.
- **Connect / Import / Login / Invite / Admin / Settings** (`connect-wizard.tsx`,
  `import-runs/[runId]/status.tsx`, `admin-import-runs.tsx`, etc.): **calm.** Same skin, trustworthy,
  no arcade ornament. **Never** style the credential form like a game.
- **Public share** (`public-share-report.tsx`, `/s/[shareSlug]` + `og.png/route.ts`): restyled,
  **privacy-safe** (manager/team name, composite + category grades, signature badges, confidence
  footer). Mobile-first. Update the OG image to the 2K look.
- **Nav/header** (`product-chrome.tsx`: LeagueNav/ProductHeader): 2K skewed tab-tiles + Tools▾;
  no raw league UUID (already cleaned per `website-fix-spec.md` — keep it clean).

## 6. Data pipeline (worker → snapshot → API → web)

Do all joins/derivations in the **worker** (`services/worker/mygm_worker/...`), bake into the
analytics snapshot, regenerate the demo fixture, re-seed. **League-agnostic** — key on owner GUID and
playerId, never on names/league id.

**6a. Per-season logos + main logo.** Source of truth = raw `espn_exports/league_<id>/season_*/core.json`
→ `.data.teams[]` (`.logo`, `.logoType`, `.primaryOwner`). One record per (team, season); season from
the **folder name**. Group by `primaryOwner` (GUID). Join to managers via
`managerKey.replace("espn-owner:","") === primaryOwner`. **Never key on `team.id`** (reused across
seasons). Emit on each manager:
```jsonc
"logo": { "main": "<url-or-local>", "mainSeason": 2026, "bySeason": { "2020": "...", ... } }
```
`main` = logo of the **latest season the owner fielded a team** (departed GMs → their final season).
Note: there is **no intra-season logo history** in the export (verified — box scores replicate the
season logo); per-season is the floor and equals "their logo that season."

**6b. Player dimension table (574 players).** Harvest from box-score rosters
(`season_*/box_scores/week_*.json`: each roster player has `id`, `fullName`, `defaultPositionId`,
`proTeamId`) + `player_lookup/player_weekly_points_flat.json` (`playerId`, `name`, `defaultPosition`,
`season`). Build `playerId → { name, position, proTeamAbbrev, latestSeason, isDST }`. Map
`proTeamId → abbrev` with ESPN's table (1 ATL,2 BUF,3 CHI,4 CIN,5 CLE,6 DAL,7 DEN,8 DET,9 GB,10 TEN,
11 IND,12 KC,13 LV,14 LAR,15 MIA,16 MIN,17 NE,18 NO,19 NYG,20 NYJ,21 PHI,22 ARI,23 PIT,24 LAC,25 SF,
26 SEA,27 TB,28 WSH,29 CAR,30 JAX,33 BAL,34 HOU; 0 = none/FA). NFL team = the player's `latestSeason`
proTeamId (most recent we have). Emit the table in the snapshot for the web to look up by `playerId`.

**6c. `playerId` on every player-bearing row.** Trades/waivers/draft already carry it
(`sides[].receivedAssets[].playerId`, `addedPlayers[].playerId`, draft `picks[].playerId`). The
**gap** is `playerLeaderboards.topSeasons/topWeeks` (only `playerName`+`position`). **Emit `playerId`
there in the worker**, backfilling by (name, season) from the flat lookup. Record-book player holders
get `playerId` too.

**6d. Signature player per GM (hero).** Definition: **max single-season points among players that GM
drafted**, across all seasons (16/16 coverage, all headshots verified). Emit:
```jsonc
"signaturePlayer": { "name": "...", "playerId": 0, "season": 0, "points": 0, "headshot": "<url>" }
```

**6e. Extend TS types** in `apps/web/lib/product-model.ts` / `product-api.ts` (and Zod schemas):
`ManagerDirectoryEntry`/`LeaderboardRow` → `logo?`, `signaturePlayer?`; `PlayerWeekRow`/
`PlayerSeasonRow`/trade-asset/waiver-player/record-holder → `playerId?`; add a `playerDirectory`
lookup type. Keep the parsers backward-compatible (fields optional; fixtures still parse).

**6f. Regenerate + re-seed** the demo snapshot fixture the alpha API serves, and the e2e mock
fixtures (`apps/web/e2e/api-mocks`).

## 7. Image system

**7a. `next.config.ts` — add:**
```ts
images: { remotePatterns: [
  { protocol: "https", hostname: "a.espncdn.com" },
  { protocol: "https", hostname: "g.espncdn.com" },
  { protocol: "https", hostname: "*.fantasy.espn.com" }, // mystique-api CUSTOM_UPLOAD
]}
```

**7b. URL templates.**
- Player headshot: `https://a.espncdn.com/i/headshots/nfl/players/full/{playerId}.png` (let `next/image` resize/optimize).
- D/ST (negative id): NFL team logo `https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png`.
- Logos: VECTOR (`g.espncdn.com`) + CUSTOM_UPLOAD (`*.fantasy.espn.com`) via `next/image`.

**7c. Bake the rot-prone logos.** Add a derivation step (near `export_espn_league.py` /
`build_player_lookup.py`) that downloads every `CUSTOM_VALID` external logo (≈20 of 70: `postimg.cc`,
etc.) into `apps/web/public/logos/<season>/<ownerGuid>.<ext>` and **rewrites those snapshot URLs to
the local `/logos/...` path**. Stable ESPN-hosted logos and headshots stay remote (CDN-cached).

**7d. Wrapper components (client, with fallback state):**
- `<TeamEmblem logo seasonOrMain name />` → renders logo on a dark plinth; `onError` → **monogram
  initials** from team/manager name. `referrerPolicy="no-referrer"`.
- `<PlayerImage playerId isDST teamAbbr name />` → headshot; `onError` → **silhouette**; D/ST →
  team logo; `loading="lazy"` (non-hero).
- `<PlayerChip playerId name teamAbbr position />` → the **headshot + NAME + TEAM + POS** chip (the
  Gibbs layout). Compact contexts may show headshot+name and reveal team/pos on hover/detail.
- All remote `<img>`/`next/image`: reserved dimensions (no layout shift), `alt` = team/player name.

**7e. Context-aware logo selection (§6a + decision 7):** season-scoped surfaces pass the season →
`logo.bySeason[season]`; career/manager surfaces use `logo.main`; Franchise Hub renders the
`bySeason` history strip. Missing key → fall back to `main` → monogram.

## 8. Motion system

**One-shot (all showcase):** ring arc sweeps to value; segmented cells fill in sequence; selection
bar slides; row→hero promote (cross-fade/scale); skewed-tab active transition; hover glow. Trigger
fills on **scroll-into-view, once**.

**Ambient (landing + dashboard ONLY):** slow animated gradient wash; reigning-GM marquee; fun-facts
ticker. Not on other pages.

**Rules:** `prefers-reduced-motion: reduce` → jump to final state, no loops; transform/opacity only
(no layout-animating props); 60fps with many rings + 574 possible images (virtualize/lazy as needed).

## 9. Responsive

Breakpoints **375 / 768 / 1280 / 1536**, no horizontal scroll anywhere.
- 375: 1-col; hero stacks; OVR ring scales down; segmented meters wrap; dense tables expose priority
  columns + push detail into row drawers; `PlayerChip` → headshot+name (team/pos in drawer); nav
  collapses to a menu.
- 768: 2-col; priority columns.
- 1280: full layout. 1536: full + max hero.
- Share card: mobile-first.

## 10. Evidence-first preservation (don't drop the substance)

- Showcase: **no confidence chip**; caveats collapsed in a tap/hover **drawer**; clean.
- Tools (`data-health`, `formula`) + caveat drawer carry **full** confidence / withheld / provenance.
- **Withheld/ineligible/unresolved-owner → `UNRATED` plate** (dimmed ring, reason on hover), **never a
  fabricated numeral.** Partial scores show the number + a small caveat marker. 2026 is in-progress →
  excluded from career by default, labeled. This is non-negotiable: never invent a score.

## 11. Edge cases & fallbacks (must all be handled)

- Dead/missing logo → monogram initials (and the ~20 CUSTOM_VALID are pre-baked so they can't rot).
- Headshot 404 / unknown player → silhouette. D/ST (negative id) → NFL team logo.
- Player row with no `playerId` after backfill → name-only chip, no broken image.
- Unresolved-owner manager (`unresolved:<season>:<teamId>`) → no GUID logo join → monogram; UNRATED.
- Departed GM → `main` logo = their final season, not 2026.
- Team/player names with apostrophes (`Mixon's Right Hook`) → render via text node, never raw HTML.
- No horizontal scroll at 375. Reserved image dimensions → no layout shift.
- Reduced-motion → all animations resolve to final state instantly.
- No raw machine ids surface in UI (keep `website-fix-spec.md`'s cleanup intact).

## 12. Constraints

- **Secrets:** web bundle gets only public Supabase URL + anon key + `NEXT_PUBLIC_API_BASE_URL`.
  No ESPN cookies, `SUPABASE_SERVICE_ROLE_KEY`, or `MYGM_CREDENTIAL_KEY_V1`. Image download runs in
  the local derivation step, not the browser.
- **League-agnostic:** no `18254195`, names, or fixture counts in product logic (tests/fixtures only).
- Keep typed routes, Zod parsing, and the API contract. Snapshot fields are additive + optional.

## 13. Phasing (internal; ONE live cutover at the end)

1. **Worker data:** per-season logos + `main`, player dimension table, `playerId` on all rows,
   `signaturePlayer`. Regenerate snapshot + e2e fixtures + extend TS/Zod types.
2. **Tokens + shell:** new token values, fonts, background, skewed-tab nav, panels (`globals.css`,
   `app-shell.css`, + the others). Rewrite `DESIGN.md`.
3. **Image layer:** `next.config` remotePatterns, bake the ~20 logos, `<TeamEmblem>/<PlayerImage>/
   <PlayerChip>` with fallbacks.
4. **Showcase surfaces:** GM Ratings (hero + promote), History, Dashboard, Franchise Hub, Season Hub,
   Players, Record Book, Trades, Waivers, Rivalries, Head-to-head — wire logos + chips per §5/§7e.
5. **Utility surfaces (calm):** connect/import/login/invite/admin/settings/data-health/formula; share card + OG.
6. **Motion + responsive passes:** §8, §9.
7. **Tests + proof gate (§14) + deploy.**

## 14. Acceptance / proof gate (nothing ships until ALL green)

- [ ] `cd apps/web && npm run typecheck` (0), `npm run lint` (clean), `npm run test` (green),
      `npm run build` (green).
- [ ] `cd apps/web && npm run e2e` green — existing specs updated to the new UI
      (`full-dashboard-flow`, `players`, `record-book`, `trades-waivers`, `season-hub`,
      `franchise-hub`, `history-landing`, `analytics`, `records-head-to-head`, `rivalries`,
      `invite-gate`, `connect-import`, `connect-invalid-credential`, `data-health-withheld-score`,
      `share-report`).
- [ ] **New tests:** image fallbacks (D/ST→team logo, 404→silhouette, dead logo→monogram), reduced-
      motion final-state, **`UNRATED` plate** for a withheld score, **per-season vs main** logo
      selection, `PlayerChip` subtitle (team+pos), `playerId` backfill on leaderboards.
- [ ] Worker: `cd services/worker && uv run pytest` green; `uv run basedpyright`; `uv run ruff check .`.
      Regenerated snapshot has `logo.{main,mainSeason,bySeason}` + `signaturePlayer` per GM,
      `playerId` on player rows, and the player dimension table.
- [ ] Readiness gates: `make verify-fixtures`, `make security-check` (**secret scan: no ESPN secrets /
      service-role / credential keys in the web bundle**), `make friend-test`, `make quality-review`,
      `make scope-fidelity-check`.
- [ ] **Deploy to Vercel** (web + alpha API as needed) and run an **automated browser screenshot
      sweep of every changed surface at 375 and 1280**, confirming: logos render (season vs main
      correct), headshot chips render with team+pos, **all fallbacks fire** (force a dead logo + a 404
      id), **zero broken images**, **no horizontal scroll**, reduced-motion respected.
- [ ] **Visual fidelity** check of the GM Ratings + hero vs `new-ui-test/mygm-menu.html`.
- [ ] Live smoke: `/connect` submits through the public API and `/import-runs/[runId]` loads
      (calm-tier styling intact).

## 15. File pointer index

- Tokens/CSS: `apps/web/app/{globals,app-shell,styles,product-surfaces,fantasy-theme}.css`
- Components: `apps/web/components/{league-history,league-dashboard,analytics-page,leaderboard-rows,
  managers-directory,franchise-hub,franchise-charts,season-hub,players-page,record-book,trades-page(+-parts),
  waivers-page(+-parts),rivalries-matrix,head-to-head-page,data-health-page,formula-page,
  public-share-report,product-chrome,status-pill,app-frame}.tsx`
- Types/data: `apps/web/lib/{product-model,product-api,api-client,env,session}.ts`; `apps/web/next.config.ts`
- Worker: `services/worker/mygm_worker/analytics/*` + `espn/lookup_*.py` + `payload.py`; derivation near
  `export_espn_league.py` / `build_player_lookup.py`
- Data sources: `espn_exports/league_18254195/season_*/core.json`, `.../box_scores/week_*.json`,
  `.../player_lookup/player_weekly_points_flat.json`
- Reference (gitignored): `new-ui-test/mygm-menu.html`, `new-ui-test/docs/*`, `new-ui-test/data/*`
- Deploy: `apps/web/vercel.json`; web `mygm-espn-alpha.vercel.app`, API `mygm-api-alpha.vercel.app`,
  `NEXT_PUBLIC_API_BASE_URL`
- Tests: `apps/web/e2e/*.spec.ts`, `apps/web/e2e/api-mocks`, vitest unit specs, `Makefile`
- Replaces: `new-ui-test/docs/implementation-handoff.md` (retired).
