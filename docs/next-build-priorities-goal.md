# MyGM — Next Build Priorities (Goal)

> Implementation goal covering four priorities: (1) unify the visual system, (2) player
> badges, (3) manager archetypes ("GM DNA"), (4) nav restructure. Every open question from
> the original brief has been resolved below — build to these decisions, not to the looser
> wording of the source brief. Where the original brief and the actual codebase conflicted,
> the codebase + the decisions here win.

## Mission

Make every page feel like it belongs to the same product as the GM Leaderboard, give every
player a defining badge and every manager an archetype identity, and collapse the nav into a
casual-friendly three-group structure with a real Home page. Build it **league-agnostically**
(works for any imported league) and **validate against league `18254195`**.

## How this app is wired (build within this architecture)

Derived analytics flow one direction; reuse it for everything new:

```
Python worker  →  analytics snapshot  →  API  →  Next.js web app
services/worker/mygm_worker/analytics/   services/api/src/mygm_api/   apps/web/lib/product-api.ts → components
```

- **Worker** (`services/worker/mygm_worker/analytics/`) computes analytics modules
  (`ratings.py`, `manager_value.py`, `draft.py`, `signature_player.py`,
  `player_leaderboards.py`, …) and assembles `payload.py` / `historian_payload.py`.
- **API** (`services/api/src/mygm_api/analytics_snapshots.py`, `analytics_responses.py`)
  serves the snapshot.
- **Web** (`apps/web/`, Next.js 16 / React 19) reads it via `lib/product-api.ts` and renders.

New badge + archetype data is computed in **new worker modules**, added to the snapshot
payload, exposed through the API contract, and consumed in the UI. No runtime computation in
the browser; no new direct-from-DB path in the web app.

Source data already present (per league, 2020–2026):
- Per-player weekly points + per-week `appliedStats` (ESPN stat IDs), `injuryStatus`,
  `box_score_appearances`: `espn_exports/league_<id>/player_lookup/player_weekly_points.json`
- Reconstructed graded trades (grades A–F, points, `net_difference`):
  `espn_exports/league_<id>/trade_grades/trade_grades.json`
- Waiver/free-agent transactions: `espn_exports/league_<id>/season_*/transactions/period_*.json`
- Draft picks: `season_*/core.json → draftDetail.picks[]`
- Season records (W/L, PF/PA): `season_*/core.json → teams[].record.overall`

---

## Decisions (resolved — do not re-litigate)

### Cross-cutting
- **Scope:** league-agnostic code; validate on league `18254195`. Handle edge cases
  (small leagues, missing seasons, players/managers absent from a season).
- **Build order:** phased and dependency-ordered, with a verification checkpoint between
  phases (see Phases below).
- **Acceptance bar per phase:** typecheck + lint pass; unit tests for all new worker
  computation (badges, archetypes, external-data joins); **and** run the app and capture
  screenshots of every affected page for visual confirmation before starting the next phase.

### Priority 1 — Unify the visual system
- **Depth:** full sweep. Extract a **shared component kit** from the GM Leaderboard and
  restyle **every** page with it (not just the four urgent ones).
- **Extract these into first-class reusable components** (today they're one-off CSS /
  inline styles in `apps/web/components/gm-ratings-board.tsx` + `app/product-surfaces.css`):
  - `TierBadge` (the Elite/High/Average pill — currently an inline `<span>` with inline style)
  - `StatBlock` ("big bold number on top, small label underneath" — unify the hero `.attr-2k`
    and row `.gm-row__micro` variants behind one component with a size prop)
  - `ManagerCard` (the `.gm-row` / `.gm-hero` card container — currently a skewed CSS grid)
  - Already reusable, reuse as-is: `OvrRing`, `SegmentedMeter` (`components/rating-visuals.tsx`),
    `TeamEmblem` (`components/team-emblem.tsx`), `PlayerImage`/`PlayerChip` (`components/player-image.tsx`)
- **Palette:** keep the **existing in-app palette** (navy `#0a0e1a`, gold `#ffe600`,
  green `#39d353`, orange `#ff9a3c`, red `#ff5c7a`, defined in `apps/web/app/globals.css`).
  The brief's hexes were approximate; the page we're standardizing on already uses these
  exact tokens. Do **not** swap in the brief's hexes.
- **Tiers:** collapse the current 4 tiers (ELITE/HIGH/MID/LOW) to **3** — **Elite / High /
  Average** — everywhere tiers are named, colored, or thresholded. This touches
  `apps/web/lib/images.ts` (`ovrTier`, `attrColor`) and the attribute-bar color thresholds,
  plus the worker if it emits tier labels. Choose sensible thresholds (e.g. Elite = top band,
  High = middle, Average = floor; no separate "Low/Bust" tier) and keep them in one documented,
  tunable place. Re-check every surface for color/label regressions after the change.
- **Pages called out as most urgent** (must look excellent; still part of the full sweep):
  History (manager cards w/ logos + badges, not plain text), Seasons (champion / runner-up as
  a true hero moment), Record Book (every record gets color + weight), Players/Leaderboards
  (position color + rank-1 visually dramatic).

### Priority 2 — Player Badges
- **Ship all 8 badges.** This includes sourcing **external NFL defense-vs-position data** to
  support **Matchup Based** (not derivable from the ESPN export alone).
- **Stat-ID mapping:** map ESPN `appliedStats` IDs to TD / yardage / receptions / targets
  (required for TD Dependent and Screen Merchant). Document the mapping in the worker.
  **Screen Merchant ships last** (needs target/reception data).
- **Window:** **single career badge per player**, computed across all seasons of data, shown
  identically everywhere the player appears.
- **Mutually exclusive:** assign the single most-defining badge per player.
- **Display:** small colored pill next to the player name, same visual style as the
  Elite/High `TierBadge`. Appears on player cards in the **trade browser, waiver browser, and
  Players leaderboard**.
- **Definitions** (from brief): Boom or Bust, High Floor, TD Dependent, Explosive, Matchup
  Based, Injury Risk, Elite Consistent, Screen Merchant. Implement thresholds in the worker,
  documented and tunable.
- **Where:** new worker module (e.g. `analytics/player_badges.py`) → snapshot → API → UI.

### Priority 3 — Manager Archetypes ("GM DNA")
- **6 archetypes** (from brief): The Gambler, The Analyst, The Opportunist, The Aggressor,
  The Stoic, The Lucky One.
- **Assignment:** one archetype per manager, computed over **full career history**.
  **Independent best-fit — duplicates allowed** (two managers can both be "The Aggressor");
  the highest signal match wins per manager. No forced league-wide uniqueness.
- **Draft signals:** use **real external historical ADP** (2020–2026) so "draft picks
  outperform ADP" (The Analyst) and "reaches on boom-or-bust players" (The Gambler) are
  literal, not proxied.
- **Signals** (from existing data + ADP): trade frequency, trade win rate / net points,
  waiver claim volume + efficiency, draft pick value vs ADP, record vs GM rating, points
  against / schedule luck. Score each manager across signals; highest match wins. Keep the
  scoring model documented and tunable.
- **One-sentence description:** generated by a **build-time LLM call** (one per manager while
  the worker builds the snapshot), result **cached into the snapshot** — not generated at
  runtime. Use a current Claude model (default to a cost-efficient one, e.g. Haiku 4.5; the
  exact model is an impl detail). The prompt is fed the manager's real numbers. **Provide a
  deterministic template fallback** so a build with no API key still produces a valid
  sentence and never hard-fails.
- **Display:**
  - Manager cards (Home leaderboard + anywhere `ManagerCard` renders): archetype name in a
    styled badge below the tier badge.
  - **Manager profile** (= the GM Rating breakdown page, see Priority 4): archetype as the
    page **headline** with the generated one-liner, above the stat breakdown.
- **Where:** new/extended worker module (e.g. `analytics/manager_archetype.py`) → snapshot →
  API → UI.

### Priority 4 — Nav Restructure + Home
Final information architecture (in `apps/web/components/product-chrome.tsx` `LeagueNav`):

- **Home** — the root route (`/leagues/[leagueId]/`). **Rebuild the existing Overview
  `LeagueDashboard` in place** into the Home design: reigning-champion hero card, GM
  leaderboard (OVR + archetype), trophy count, and **league news = an auto-generated activity
  feed** derived from existing snapshot data (latest champion crowned, recent graded trades,
  notable waiver pickups, records broken — no authoring system). `/overview` becomes an alias
  of Home.
- **My League ▾** — History · Seasons · Rivalries · Record Book · **Players**
- **Tools ▾** — Trade Browser · Waiver Browser · Head-to-Head · GM Rating breakdown
- **Canonical manager profile = the GM Rating breakdown page** (`/gms/[managerId]`). The
  archetype headline + one-liner live here. **Every clickable manager name across the app**
  (leaderboard, history, rivalries, trade browser, etc.) routes here. (Mind the identity
  mapping: profile is `/gms/[managerId]`; the Franchise Hub uses `/managers/[managerKey]` —
  resolve consistently.)
- **Franchise Hub** (`/managers/[managerKey]`: career stock chart, season timeline,
  trade/waiver ledgers, rivalry data) — **kept as a separate "franchise history" page**,
  linked from the profile. Not retired.
- **Formula explainer** — linked **only from the GM Rating breakdown profile** ("How the
  rating works"). Not a Tools item.
- **Hidden from main nav** (still reachable by direct URL / admin): Managers directory
  (`/managers` index — redundant once Home leaderboard + clickable names exist), Data Health
  (Jake/admin only), Settings + Share Management (hide until sharing ships), legacy
  `/records` → **redirect to Record Book** (`/record-book`).

### External data handling (Priorities 2 & 3)
- **Fetch once, vendor as static per-season files** committed into the repo/snapshot inputs;
  refresh manually each new season. Reproducible builds, no runtime network dependency, fits
  the public-dataset model.
  - NFL defense-vs-position (for Matchup Based): e.g. nflverse / `nfl_data_py`.
  - Historical ADP (for archetype draft signals): a chosen fantasy-data source.
- **Check each source's license before redistribution** — the ESPN export is intended to be a
  shareable public dataset, so vendored third-party data must be redistributable (or kept out
  of the public bundle).

---

## Phases (build in this order; verify before advancing)

**Phase 1 — Design-system kit + full restyle.**
Extract `TierBadge`, `StatBlock`, `ManagerCard`; collapse tiers to 3 in `lib/images.ts` and
the worker; restyle every page using the kit, prioritizing History, Seasons, Record Book,
Players. Acceptance: typecheck/lint, run app, screenshot every page.

**Phase 2 — Nav restructure + Home + clickable names.**
Implement the Home/My League/Tools structure; rebuild Overview-in-place as Home with the
champion hero, leaderboard, trophy count, and activity feed (data already in snapshot);
route all manager names to `/gms/[managerId]`; add hides/redirects (`/records`, `/overview`,
Managers directory, Data Health, Settings/Share). Acceptance: typecheck/lint, run app,
screenshot Home + each dropdown destination + a profile reached by clicking a name.

**Phase 3 — Manager Archetypes.**
Vendor ADP data; build the archetype worker module + signals + scoring; add build-time LLM
one-liner (with template fallback); surface snapshot through API; render archetype badge on
manager cards and the headline on the profile. Acceptance: unit tests for signal scoring +
assignment, typecheck/lint, run app, screenshots of Home cards + a profile headline.

**Phase 4 — Player Badges.**
Map ESPN `appliedStats` IDs; vendor NFL defense-vs-position data; build the badge worker
module (all 8, Screen Merchant last) + career-window computation; expose via API; render
badge pills on player cards in trade browser, waiver browser, Players leaderboard.
Acceptance: unit tests for each badge rule, typecheck/lint, run app, screenshots of player
cards on all three surfaces.

---

## Out of scope / explicitly deferred
- Switching to the brief's literal hex palette (rejected — keep existing tokens).
- Forced league-wide unique archetypes (rejected — independent best-fit).
- Runtime/browser computation of badges or archetypes (everything is snapshot-baked).
- A content-authoring system for league news (it's an auto feed).
- Sharing/Share Management UI (hidden until sharing ships).
