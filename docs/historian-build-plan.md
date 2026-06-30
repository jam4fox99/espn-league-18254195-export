# MyGM — "League Historian" build plan

## Vision
Turn MyGM from a database-with-a-viewer into a **backward-looking league historian**: a
place to look back through the seasons, see every manager's roster decisions and career
arc, and settle "who's actually the best GM" with receipts. FantasyPros is forward-looking
("who do I start?"); our edge is backward-looking ("who was actually good, proven").

The user cares more about **browsing history and roster decisions across seasons** than
about precise scores. Tone is **neutral** (factual superlatives with receipts, no roasting).

## Locked decisions (from interview)
- **Scope:** full build, phased (each phase shippable).
- **Persistence:** snapshot-only, **no database**. Everything computed in the Python worker,
  baked into the analytics snapshot JSON, served from the in-memory store. No commissioner
  edit/merge tool (demo league is already fully resolved by ESPN owner UUID).
- **v2 GM rating** replaces the broken v1 (v1's trade/waiver components are league-wide
  constants — identical for every manager; see `services/worker/mygm_worker/analytics/ratings.py:101-102`).
- **IA:** dual hubs (Managers × Seasons) on a **League-History landing timeline**; existing
  analytics pages survive as secondary "tools."
- **Tone:** neutral superlatives, receipts attached. No roast voice.
- **Wrapped:** "Season-in-Review" baked into each Season Hub; swipeable/shareable-image
  version is a fast-follow (out of scope this build).
- **Charts:** `recharts` (radar, line, heatmap, bars).

## Data foundation (verified available)
All in `tests/fixtures/espn/league_18254195/` and the worker:
- Per-week per-player points incl. **bench vs starter** (`isStarter`, `lineupSlotId`) —
  `player_lookup/player_weekly_points.json`, `services/worker/mygm_worker/espn/lookup_*.py`.
- Weekly matchup scores, `isPlayoff` populated (84 playoff matchups in fixture).
- **Final standings / champion:** `rankCalculatedFinal` per team in `season_*/core.json`
  (rank 1 = champion), plus `playoffSeed`. NOT yet extracted by the worker.
- Draft picks (order, round, slot, teamId) in `data.draftDetail.picks[*]`. **No ADP.**
- Trades with per-side players + post-trade points; waivers with added/dropped
  rest-of-season points + drop-regret. FAAB bid amounts are all 0 (unusable).
- Manager identity already stitched across seasons by ESPN owner UUID
  (`services/worker/mygm_worker/analytics/identity.py`), exposed as `managers[*].aliases`.

## v2 GM rating spec
File: `services/worker/mygm_worker/analytics/ratings.py` (new `mygm-historian-v2`, keep v1).
Per-manager, per-season components, each **percentile-ranked 0–100 among that season's
managers**, then weighted:

| Component | Real per-manager measure | Weight |
|---|---|---|
| Trade value | Σ net points from their trades (received − sent), from `trades.items[*].sides` | 0.25 |
| Waiver/FA value | Σ `netPoints` of their score-eligible waiver/FA moves | 0.25 |
| Lineup efficiency | season avg of `started_points / optimal_lineup_points` per week | 0.15 |
| Record & points | existing: 0.6·points-for percentile + 0.4·win% | 0.35 |

- **Luck component removed** entirely (not computed, not shown).
- Career score = mean of season scores (unchanged aggregation), 2026 excluded by default.
- Lineup efficiency needs the league's lineup-slot settings (from `core.json` roster
  settings) + `eligibleSlots` per player to compute the optimal legal lineup each week.
- v1 remains viewable via the existing `formulaVersion` mechanism.

## New / extended worker analytics (→ snapshot)
- `standings.py` (new): extract `rankCalculatedFinal`, `playoffSeed` → per-season final
  standings, champion, playoff appearances. Enrich `seasons[*]` and `managers[*]`.
- `lineup_efficiency.py` (new): optimal-vs-actual per manager-week-season; feeds rating +
  a bench/efficiency leaderboard.
- `manager_value.py` (new): per-manager trade value + waiver value rollups (also reused by
  the rating). Favorite trade partners, lifetime net trade value.
- `draft.py` (new): draft recap per season; retrospective "steals/busts" = pick slot vs.
  within-draft points rank (no ADP).
- `career.py` (new): per-manager career stat line (all-time record, total points, titles,
  playoff apps, best/worst season, avg rating) + auto **eras** (dynasty = ≥2 consecutive
  top-3 finishes/titles; drought = ≥2 consecutive bottom-third). 
- `rivalries.py` (new or extend `head_to_head.py`): full all-play **matrix** + per-manager
  Nemesis / Favorite Opponent from existing pair data.
- Extend `records.py`: add Bench Points Leader, Waiver Value Leader, Best/Worst Trade,
  Draft Steal of the Year (neutral superlatives, each with manager + value + season).
- `payload.py`: serialize all of the above into new snapshot sections:
  `managers[*].career`, `seasons[*].{champion,finalStandings,draftRecap,superlatives}`,
  `rivalries`, `playerLeaderboards`, `lineupEfficiency`, extended `records`.

## New / extended API (read from enriched snapshot)
`services/api/src/mygm_api/routers/analytics.py` + schemas:
- `GET /leagues/{id}/history` — league timeline (seasons w/ champion + headline).
- `GET /leagues/{id}/managers/{managerKey}` (Franchise Hub aggregate; supersedes thin
  `/gms/{manager_id}`): career line, season timeline, trophies, eras, rivalries, value.
- `GET /leagues/{id}/seasons/{year}` (Season Hub aggregate; extend existing): standings,
  champion, draft recap, moves, season-in-review.
- `GET /leagues/{id}/rivalries` — matrix + per-pair.
- `GET /leagues/{id}/players/leaderboards` — league-wide player leaderboards.
- Flesh out the stub `players/{id}/weekly-points`.
All gated by existing `require_league_access`; demo seeded via `seed_demo.py` (unchanged).

## Web (Next.js, `apps/web`)
Add `recharts`. Restructure `LeagueNav` (`components/product-chrome.tsx`) to:
**History · Managers · Seasons · Rivalries · Record Book · Players · (Tools ▾)**.
New/upgraded pages under `app/leagues/[leagueId]/`:
- `/` → **League History timeline** (landing; replaces bare dashboard as front door).
- `/managers` + `/managers/[managerKey]` → **Franchise Hub** (career line, season timeline,
  trophy case, eras, radar chart, franchise stock line chart, trade ledger, nemesis).
- `/seasons/[year]` → **Season Hub** (standings, champion, draft recap, all moves,
  Season-in-Review).
- `/rivalries` (+ detail) → all-play **matrix heatmap**, per-rivalry page.
- `/record-book` → superlatives + records, neutral, with receipts.
- `/players` → player leaderboards + lineup-efficiency leaderboard.
Existing trade/waiver browsers + GM leaderboard kept as secondary tools.
Charts: radar (rating components), line (franchise stock), heatmap (rivalry matrix), bars.
Reuse the compact `LeaderboardRows` / `record-card` / `lb-*` styles already built.

## CUT / out of scope
- Trade *network* force-graph → replaced by per-manager trade ledger + rivalry matrix.
- All-play / luck records → cut (user dropped luck).
- Swipeable Wrapped + auto share-images → fast-follow.
- ADP-based draft *grades* → impossible (no ADP); retrospective steals/busts instead.
- Database + commissioner merge/edit tool → separate future project.

## Phasing (each phase = usable, tested, deployable)
1. **Worker foundation:** standings/champion extraction, manager trade/waiver value,
   lineup efficiency, draft recap, career rollups; `recharts` installed. Regenerate snapshot.
2. **v2 rating** live: new components on leaderboard + GM pages; v1 toggle preserved.
3. **IA restructure + League History landing** + new nav.
4. **Franchise Hub** (career line, timeline, trophies, eras, radar, stock chart, ledger).
5. **Season Hub** (standings, champion, draft recap, moves, Season-in-Review).
6. **Rivalries** (matrix + nemesis + per-rivalry page).
7. **Record Book + Player tier** (superlatives, player & lineup-efficiency leaderboards).

## Verification (per phase)
- Worker: pytest characterization tests for new analytics; regenerate
  `analytics_snapshot.json` and re-seed.
- API: contract tests for new/changed endpoints.
- Web: `tsc --noEmit`, `biome check`, `vitest`, `playwright`; live screenshot sweep of
  changed pages on the deployed demo (`https://mygm-espn-alpha.vercel.app`).
- Deploy each shippable phase to Vercel (web + API as needed) and confirm on the live demo.
