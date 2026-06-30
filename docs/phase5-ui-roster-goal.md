# Goal — Phase 5: Roster history, universal filters, custom controls & visual overhaul

You are completing a locked, multi-phase build for **MyGM** (ESPN fantasy-football
analytics). Drive each phase to its verification gate and proceed; **end by deploying
web + API to Vercel**. Do not pause to ask the user — every product decision below is
already settled (it came out of a grilling interview).

This builds directly on the shipped `mygm-fixes` work (VOR engine, V3 GM rating, League
News, trade grades/veto, draft cards). **Snapshot-based** this batch (no live ESPN
calls). **League-agnostic**: derive every constant from settings/data (starting-lineup
slots from `lineupSlotCounts`, etc.) and validate against league `18254195`.

---

## Non-negotiable constraints (apply to every phase)

**Worker (`services/worker`)**
- `basedpyright` (typeCheckingMode=all) and `ruff` (select=ALL) must be clean on all
  files you add or touch. (Two PRE-EXISTING test files — `test_manager_archetype.py`,
  `test_player_badges.py` — already have pyright errors unrelated to this work; don't
  make them worse, but you don't have to fix them.)
- PEP 695 generics, `math.sqrt`, `dataclasses`, and the `json_tools` helpers
  (`as_object`, `as_array`, `string_value`, `int_value`, `float_value`) — never
  `json.loads`. Tests must use the same typed-access helpers (mirror
  `tests/analytics/test_fixture_analysis.py`).
- New analytics derive from existing fixture data only: `reader.core(season)` →
  `settings.lineupSlotCounts`; `reader.player_lookup()` → per-player
  `box_score_appearances` (`isStarter`, `lineupSlotId`, `lineupSlot`, `season`, `week`),
  `weekly_points`, `defaultPositionId`; `reader.seasons()` → `SeasonMeta.final_week`;
  `waiver_moves.manager_waiver_scores` / `waiver_move_rows`.

**API (`services/api`)**
- New response models are `ApiModel` subclasses with explicit `Field(alias=...)`
  (camelCase out). Pass-through blobs use `SnapshotJsonObject`. New endpoints follow the
  existing `routers/analytics.py` pattern (`require_league_access` +
  `require_current_snapshot`). Franchise-hub additions ride on `manager_hub` /
  `_manager_section`.

**Web (`apps/web`)**
- Next 16 / React 19 / TS `exactOptionalPropertyTypes` + `typedRoutes`. `tsc --noEmit`
  and `biome check .` must be clean. Zod schemas use `.passthrough()` +
  `.catch(...)`. Any new per-row field must be added to the **explicit object literals**
  that copy rows (e.g. `analytics-page.tsx` `GmLeaderboard`, `franchise-hub.tsx`) or it
  is silently dropped. Dynamic hrefs/redirects cast `as Route`.

**Verification gate between every phase:** worker `ruff` + `basedpyright` + `pytest`;
API `ruff` + `pytest`; web `tsc` + `biome`. Regenerate the snapshot and re-run the full
worker suite whenever worker analytics change.

---

## Phase 1 — Worker: roster-history engines + waiver superlatives

### 1A. Franchise roster views (`services/worker/mygm_worker/analytics/roster_history.py`, new)
Per manager, derive all of the following from box-score `box_score_appearances` +
`weekly_points`, with starting slots read from `lineupSlotCounts` (league-agnostic — do
NOT hardcode QB/RB/WR/TE/FLEX/K/DST counts):

- **All-Time Lineup** — for each *starting* slot, the single best player-**season** the
  manager **started** at that slot (started, never benched), ranked by **points per game
  over the weeks they were started at that slot**, with a **minimum of 3 started games**
  at that slot that season. FLEX/superflex = best leftover eligible player not already
  claimed by a base slot. Distinct players across slots. Each entry carries: playerId,
  name, position, slot, season, ppg, gamesStarted, totalPoints (secondary), proTeam.
- **All-Time Depth Chart** — same rule, but 1st/2nd/3rd best per position bucket.
- **All-Time by Total Points** — the same all-time lineup ranked by **total season
  points** instead of PPG (emit alongside so the web can toggle between PPG ↔ total).
- **Most-Started Cornerstones** — players ranked by **total weeks started** for this
  manager across their whole tenure (name, weeksStarted, seasons span, totalPoints).
- **Best Single Season** — the manager's single best season (by that season's GM-rating
  or points-for — pick the documented metric) and its full starting lineup snapshot.
- **Season-by-Season Rosters** — each season's **final-week** roster (use
  `SeasonMeta.final_week`), full roster grouped by position, with player name + position
  + that season's total points + started/bench flag.

Provide a `roster_history(reader, managers, team_seasons) -> dict[str, JsonObject]`
keyed by manager. Add `tests/analytics/test_roster_history.py` (typed-access helpers):
all-time lineup fills every starting slot with distinct players, the 3-game floor is
enforced, depth chart has ≥1 per filled position, season-by-season covers every included
season, cornerstones rank by weeks started.

### 1B. Waiver superlatives (extend `waiver_moves.py`)
Add a `waiver_superlatives(rows, *, names) -> dict[int, JsonObject]` keyed by season,
each with: **bestPickup** (max rest-of-season points/VOR added), **worstDrop** (max
points/VOR dropped & lost), **bestWireValue** (max net VOR — savviest), **mostActive**
(most eligible moves). Each card = {managerKey, displayName, headline value, player or
count, detail}. Test season-scoping + that the four cards resolve for 2025.

Wire 1A + 1B into the snapshot via `payload.py` (new top-level `rosterHistory` map and a
`waiverSuperlatives` map; attach `rosterHistory[managerKey]` onto the manager row like
`draftCard`). Regenerate the snapshot + `bake_logos.py` mirror; update
`test_fixture_analysis.py` assertions.

---

## Phase 2 — API + web data plumbing

- **API:** `manager_hub` response gains `rosterHistory` (pass-through
  `SnapshotJsonObject` from `_manager_section(manager, "rosterHistory")`). Add a
  `waiverSuperlatives` field to the waivers section response (or a small dedicated
  endpoint) keyed by season. Keep pyright/ruff clean.
- **Web:** extend `managerHubSchema` (`rosterHistory`, passthrough + typed sub-schemas)
  and the waivers reader (`waiverSuperlatives`). Export the new types. Add the new fields
  to every explicit row-copy literal.

---

## Phase 3 — Universal filter system + custom select component

### 3A. Reusable controls (`apps/web/components/controls/`, new)
- **`<Select>`** and **`<MultiSelect>`** — fully styled dropdown/listbox (button +
  popover), keyboard-accessible (arrow keys, Enter, Esc, type-ahead), matching the
  site's dark 2K aesthetic. **Replace ALL native `<select>`** (14 across
  `trades-page.tsx` 95/106/116, `waivers-page.tsx` 135/146/162/172,
  `connect-wizard.tsx`; head-to-head is retired). No more native macOS dropdowns
  anywhere.
- **`<FilterBar>`** — shared faceted filter: each facet renders **stackable
  removable chips** via `<MultiSelect>`; **OR within a facet, AND across facets**. Plus a
  free-text **search** box and a **sort** dropdown. Shows "N of M" result count. Manages
  filter state generically (facet key → selected values[]).

### 3B. Apply to every browser (replace the bespoke per-page logic)
- **Trades** (`trades-page.tsx` / `trades-page-parts.tsx`): facets = Manager · Grade
  (A+…F buckets) · Season · Veto band. Retire the "View mode" select — replace with the
  sort dropdown (Best value / Most lopsided / Newest) + (Phase 4) superlative header.
- **Waivers** (`waivers-page.tsx` / `waivers-page-parts.tsx`): facets = Manager · Type
  (waiver/FA) · Add/Drop · Season. Retire "View mode" → sort + the **waiver superlative
  header cards** (Best Pickup · Worst Drop · Best FA Value (VOR) · Most Active) ABOVE the
  list. Rewrite `filterTrades`/`filterMoves` to consume the generic FilterBar state.
- **Players browser**: facets = Position · Manager · Season (apply the same FilterBar).

---

## Phase 4 — Visual overhaul

### 4A. GM attribute bars (`rating-visuals.tsx` `SegmentedMeter`, used by GM profile /
leaderboard / franchise hub)
- Segments become **chevron / arrow shapes** (▶), not flat rectangles.
- Coloring = **red→green spectrum ramp**: the bar is a fixed left-to-right red→green
  gradient and the fill reveals it, so a low score lights only the red end and a high
  score climbs into green. Unfilled chevrons are dim. Keep the staggered fill animation.
  Keep the chevron shape as a deliberate angular accent (see rounding below).

### 4B. Aliases box (in `analytics-page.tsx` ManagerReport **and** the Franchise Hub
aliases block)
- Replace the cramped comma string with a responsive **grid of alias cards**: each card =
  that season's **team logo** (`selectLogo(hub.logo, season)` — per-season lookup already
  exists), team name, and year. Clean, evenly sized, rounded cards.

### 4C. League News layout fix (`league-news-page.tsx` + `.news-feed`/`.news-item` CSS)
- The left "Headlines" column currently collapses to a vertical sliver wrapping one word
  per line. Rebuild each news item as a proper full-width card (icon + title + body +
  grade/veto badges laid out horizontally/stacked sensibly) that fills the left column.
  Keep the team-strengths sidebar but ensure the 2-col grid gives Headlines real width.

### 4D. Record Book cleanup (`record-book.tsx` + `.record-grid`/`.record-card` CSS)
- Tighten the grid, spacing, and card styling so groups (Career / Scoring / Matchups /
  …) read cleanly and consistently; rounded cards; clear value emphasis.

### 4E. Round all the edges — **subtle (~8px) everywhere**
- Bump the global radii (`globals.css` `--radius-control` 4→8px, `--radius-panel` 6→10px;
  reconcile the hardcoded `data-table` 14px). Round chips, inputs, dropdowns, buttons,
  cards, tables. **Keep** the angular nav tabs + chevron bars as the 2K signature, just
  softened slightly. No hard 0-radius corners left anywhere.

---

## Phase 5 — Verify & deploy

Full gate (worker ruff+pyright+pytest, API ruff+pytest, web tsc+biome), regenerate +
mirror the snapshot, then **deploy both apps to Vercel production**: from
`apps/web` and `services/api` run `vercel deploy --prod --yes` (projects
`mygm-espn-alpha` / `mygm-api-alpha`). Report the production URLs and a per-phase summary
of what shipped vs. anything deferred.
