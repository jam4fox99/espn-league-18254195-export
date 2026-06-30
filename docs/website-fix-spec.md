# Website fix spec — GM rating + identifier cleanup

Goal: the GM rating page must work, and the UI must stop showing raw machine
identifiers (league UUIDs, `trade:2020:…`, `espn-owner:{…}`, version UUIDs).

## Render-breaking bugs
- **GM leaderboard `/gms`** and **Season overview `/seasons/{year}`** crash: these
  endpoints return the snapshot-rows envelope `{modelName, modelVersion, rows}`, but
  the web `readAnalytics`/`parseAnalyticsPayload` only accepts the analytics-collection
  shape (requires `confidence` + `sourceCoverage`). The fallback `fixturePayloadSchema.parse`
  then throws `expected object, path: dashboard`.
- **Manager report `/gms/{id}`** renders with no score/components: the endpoint returned
  a profile only (`managerKey, displayName, teamAliases, scoreEligible, caveats`).
- **Dashboard landing page** showed an empty "All-time leaderboard": the `/dashboard`
  summary endpoint did not include the leaderboard the web table reads.
- **Head-to-head** leaked raw `managerKey`s in the manager pickers and the matchup
  "Winner" column (`winnerKey`).

## Code-like identifiers shown to users
- League UUID — `product-chrome.tsx` ProductHeader, on every page.
- Version UUIDs — dashboard, trades, waivers, season, formula metric strips; the
  formula "Career caveat" string; the "Recompute snapshot" status run id.
- `managerKey` (`espn-owner:{…}`, `unresolved:2020:0`) — GM leaderboard, trades,
  waivers, records, head-to-head.
- `trade:2020:uuid` / `waiver:2020:uuid` ids and `sourceTransactionId` UUIDs — trades
  and waivers tables/detail.

## Fixes
1. API (`analytics_snapshots.py`, `schemas.py`, `routers/analytics.py`): resolve
   managerKey → displayName / latest teamName from `snapshot.managers` (via `_label_map`
   + `_labelled`) and attach human fields to leaderboard, trades, waivers and records
   rows; enrich `/gms/{id}` with the manager's leaderboard score, confidence and labelled
   component breakdown; add the name-enriched leaderboard to the `/dashboard` response;
   replace the formula `caveat` (which embedded the version UUID) with a plain retrospective note.
2. Web: accept the snapshot-rows shape in `parseAnalyticsPayload` (fixes the GM + Season
   crash); render displayName/teamName instead of keys; show "Current" instead of version
   UUIDs; show human trade/waiver titles (`rowTitle` → constructed fallback, never the raw
   id) with a source-transaction count instead of raw ids; drop the league UUID from the
   header; resolve head-to-head winner keys to names; drop the run id from the recompute status.
3. Tests: regenerate stale e2e assertions that asserted the removed ids/old headings, add
   the missing required "ESPN league ID" step to the connect spec, and add web unit
   regressions for the GM snapshot-rows parse + manager-report enrichment.

## Known limitation
Head-to-head aggregate stats (all-time record, average score, biggest win) come from the
snapshot pair payload, which does not yet carry them, so they render as 0 / "Unavailable".
This is a data-pipeline gap, not an identifier leak, and is out of scope for this fix.

## Verification (all green)
`tsc --noEmit` (0), `biome check` (clean), `vitest run` (13), `playwright test` (9),
API contract tests (15). Plus a live scan of every product endpoint confirming each
rendered field is human-readable — no `espn-owner:`, `trade:`, `waiver:` or bare UUIDs
in displayed text (managerKey remains only inside the encoded profile-link URL).

---

# UI revamp — fantasy dashboard (RotoBot theme)

Goal: replace the bare-bones light UI with a dark fantasy-platform look (RotoBot
reference theme) and surface player-level data everywhere.

## "Unresolved manager vs Unresolved manager"
25 of 95 trades are 2020 events whose ESPN source had "0 TRADE items", so the
counterparty, teams and players are unrecoverable. These are now filtered out of the
trade browser (`hasTradeSides`) and reported as an "N early-season trades omitted" count
on the metric strip, instead of rendering empty "Unresolved manager" rows. The API also
enriches each trade `side` with its resolved `managerName`/`teamName`.

## Design system
- `app/globals.css`: `:root` retoned to the RotoBot dark palette (bg `#030712`, raised
  `#0b0f18`/`#101828`, cyan brand `#00d3f2`, border `#1e2939`, grade + category accents),
  ambient radial-gradient page background.
- `next/font`: Rubik (UI) + JetBrains Mono (numbers) wired via `--font-sans`/`--font-mono`.
- `app/fantasy-theme.css` (new, imported last): elevates shared classes (panels, metric
  strip, tables, status pills, nav with active state) and adds rich components — grade
  badges, player chips, the trade analyzer card, score-component bars, rank badges.

## Rich surfaces
- **Trades**: manager-vs-manager analyzer cards — each side shows manager + team, an
  A+…F grade badge, value swing, and the players received (name + post-trade points).
- **Waivers**: add/drop rows with green/red player chips, points, manager + team, drop
  regret (capped at 60 with a "showing N of M" note over ~3,900 moves).
- **GM leaderboard / dashboard**: ranked rows with gold/silver/bronze rank badges, big
  numeric scores, and per-component score bars.
- **Manager card**: score, component score bars (with weights), team aliases.

Live visual check: all 9 league pages render with zero console errors, zero code-id
leaks, and player/manager names throughout.
