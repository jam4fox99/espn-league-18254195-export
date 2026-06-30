# MyGM Fixes — Build Goal (locked spec)

> Paste this whole file into `/goal` with a Stop hook. **Treat the completion
> condition itself as your directive: do not pause to ask the user what to do —
> drive each phase to its verification gate and proceed.**

## Mission

Ship the next batch of MyGM fixes: fix QB-inflated trade/waiver value with a real
**Value-Over-Replacement (VOR)** engine, rebuild the trade-grade curve, add a
**draft-graded V3 GM rating**, a dynamic **League News** intelligence layer, and a
set of new surfaces (all-time lineups, year-by-year rosters, draft board, asset
trade-trees, veto-likelihood) — then consolidate redundant nav.

## Non-negotiable constraints

- **League-agnostic, validated against league `18254195`.** Every computation
  derives its constants from league settings/data (lineup slots, scoring weights,
  team count) — never hardcode league specifics. Validate output against the
  demo league each phase.
- **Snapshot-based this batch; live ESPN ingestion is a deferred follow-on epic.**
  Build every "real-time" brain (league news, trade rating, suggestions) against
  the **most-recent season in the snapshot**, and architect each so that "live"
  later is just running the same pipeline on fresher data. Do **not** build the
  ingestion/polling infra now.
- **League News = most-recent season only.** Everything older lives in the
  History tab.
- **Natural-language prose = hybrid.** Facts come from deterministic templates
  (always on, fully testable, never hallucinate). An LLM polishes phrasing only
  when a `MYGM_*_LLM` flag + API key are present — exactly the existing
  `MYGM_ARCHETYPE_LLM` pattern. Tests and key-less builds use the template path.
- **Worker conventions hold:** dependency-free stdlib + dataclasses; `json_tools`
  helpers (never `json.loads`); `basedpyright` typeCheckingMode=all + `ruff`
  select=ALL clean; PEP 695 generics; `math.sqrt`. Web: Next 16 / React 19 / TS
  (`exactOptionalPropertyTypes`, typedRoutes); Biome clean; Zod `.passthrough()`
  + `.catch(undefined)`; new per-row fields must be added to the explicit object
  literals in `analytics-page.tsx` (`GmLeaderboard`) or they're silently dropped.
- **End with a Vercel deploy** of web + API (`vercel deploy --prod --yes` from each
  app dir) after the final phase verifies.

## Verification gate (run between every phase)

1. **Typecheck + lint clean** — `basedpyright` (all) + `ruff` (ALL) for the worker;
   `tsc`/Biome for web.
2. **Unit tests for every new worker computation** — VOR, replacement levels, fit,
   grade curve, draft surplus, veto-likelihood, new records, asset lineage,
   waiver suggestions. Cover edge cases (DNP weeks, keepers, missing-season ADP,
   early-season fit fallback).
3. **Run the app on demo data + screenshot affected pages** via the local harness
   (API with `MYGM_SEED_DEMO=1`, `next dev` on 3000, throwaway Playwright spec →
   absolute scratchpad path). After worker changes: regen snapshot
   (`analyze-fixture`) **then** `scripts/bake_logos.py`, and restart uvicorn.

---

## Phase 1 — VOR value engine + trade re-grading

**Goal:** kill QB inflation and the bimodal A+/F distribution.

### VOR engine (new `analytics/vor.py` or equiv.)
- **Value Over Replacement**, computed **per season**, on a **per-week** basis:
  a player's value over a window = Σ over weeks of `(player_week_pts −
  replacement_pts_for_his_position_that_season_per_week)`.
- **Replacement = "last starter"** at each position, from **all NFL players** at
  that position (the objective startable pool, not just league-rostered).
  Replacement rank ties to league starter demand (slots × teams + flex
  allocation), read from each season's lineup settings. Typical 12-team/1-QB:
  QB ≈ rank 12-13, RB ≈ 30, WR ≈ 36, TE ≈ 13.
- **QB anchor:** replacement QB = last-startable QB (~QB12-13, ≈ **18 PPG**),
  **per-season**, exposed as a **tunable constant**. Sanity-check the build so
  only ~elite QBs (≈23-25+ PPG) carry strong value and a stud RB still outranks
  an elite QB; if good QBs still inflate, nudge the line up to the QB10 (~20 PPG)
  level. Do **not** hardcode 24.
- Skip DNP weeks (empty `appliedStats` + 0 pts) as already established for badges.

### Scope of VOR (Layer 1)
- **Trade grades** and **waiver value/grades** switch to VOR.
- **Player leaderboards** (top weeks / top seasons) stay on **raw points** — "most
  fantasy points" is a real record.
- **Player badges** stay on **raw points** (already position-relative).
- (The OVR rating's trade/waiver *components* also move to VOR — see Phase 2.)

### Re-grading model
- Realized trade value uses the **existing scoring window** — the week after the
  trade through season-end (per `trade_summary.py`); waiver value keeps its
  existing per-move window. VOR replaces raw points *inside* those windows.
- `value_score` = a **saturating transform** of the VOR net (e.g. logistic/tanh)
  so a +200 and a +80 net both map near the top instead of racing to extremes —
  this alone kills most bimodality.
- **Roster fit** (need): at the trade's scoring period, each team's
  **season-to-date points-by-position from started players**, ranked vs the
  league that season. Bottom-third = need, top-third = strength. Early-season
  (<~3 weeks of data) → fall back to prior-season positional finish; no signal →
  fit contributes 0. **Fit runs on QB/RB/WR/TE only** (K/DST excluded from need;
  they still contribute their tiny VOR value).
- `fit_score` ∈ [0,1] per side from acquired players hitting needs.
- **`composite = 0.65·value_score + 0.35·fit_score`**, per side.
- **Full rescue:** fit can lift a points-loss up (a genuine need-fill can reach
  C/B), not just temper a win.
- **Grade mapping = calibrated absolute thresholds, full granularity**
  (A+, A, A-, B+, B, B-, C+, C, C-, D+, D, D-, F). Fixed cutoffs tuned once from
  the league's real composite spread so the distribution is bell-shaped:
  **A+ and F genuinely rare (~3-5% each), fat middle in B/C (~55-60%)**. Grades
  are **permanent/stable** (a trade's grade never changes because of other trades)
  — NOT a percentile curve.
- Same VOR drives **waiver value** (`waiver_moves.py` / `manager_waiver_scores`).

### Bug fix
- **`_trade_summary(row, manager_key)` (`manager_value.py`)**: currently collects
  `receivedAssets` from **all** sides, so both sides of a trade list the same
  players (the "Navid +461.4 / Gus −461.4 both acquired the same four" bug). Fix
  to filter received assets to the side that belongs to `manager_key`.

---

## Phase 2 — OVR V3 rating + draft analytics

### Draft grade (extend `analytics/draft.py`)
- **Outcome surplus in VOR**: per pick, `surplus = VOR_actual − VOR_expected_for_slot`,
  where the expectation = a **pooled draft-slot→points curve** fit across **all**
  the league's drafts (robust, needs no ADP → works for every season incl. 2025).
  Per-manager season + career draft grade = Σ surplus.
- **Reach/value vs ADP = flavor only**: annotate each pick with its ADP and
  reach/value ("took at 15, ADP 32"); show a reach indicator. ADP is **not** the
  grade baseline.
- **Keepers excluded** from surplus (already filtered).
- **2025 ADP gap:** grade is unaffected (slot-based). Try to fetch 2025 ADP for
  the reach flavor; if unavailable, blank only the reach flavor for 2025 and
  degrade gracefully.

### OVR V3 formula (`ratings.py`)
- New formula version superseding v2. **Components & weights:**
  **Trade 20 (VOR) / Waiver 20 (VOR) / Lineup 15 / Record 20 / Draft 15 / Luck 10.**
  (Tunable; lineup efficiency = the "choosing who to start" criterion; luck
  restored.)
- **Trade & waiver components use VOR** (consistency with the new grades).
- Add the **Draft** bar to the GM-rating component breakdown; add the per-manager
  **draft career card** (career surplus, best/worst picks) — it lives on the
  **Franchise Hub** (Phase 5), with "best draft pick" echoed in the profile's
  highlight cards.
- **Fix the stale formula-explainer page** (`formula-page.tsx` hardcodes the old
  35/35/20/10 v1 and ignores its fetched data) → render the actual live V3.

---

## Phase 3 — Records, trade highlights, asset trade-tree, veto-likelihood

### New records (`records.py`)
- **Most points all-time (per manager)** = a manager's career total points
  (regular season + playoffs) — a per-manager record, not a player record.
- **Highest PPG per manager** = career points ÷ games, **min 16 games** to qualify.
- Surface both in the Record Book and the news feed.

### Trade highlights
- **Best & Worst trade forced to be *different* underlying trades** (Best = best
  graded side; Worst = lowest graded side from a different trade) so the feed
  isn't one lopsided deal shown twice.
- **Most Even / Fair Trade** = the trade with the **smallest VOR value gap**, gated
  so both sides exchanged meaningful value (no trivial nothing-trades), tie-broken
  toward **both sides filling a need**. Front-page highlight naming both managers.
- Lightweight per-manager **"fair trader"** stat on the profile.

### Asset trade-tree / journey (separate view — does NOT change grades or OVR)
- New context view on the Trade Browser: click a trade → trace each asset's
  **lineage** through the manager's dated transaction timeline (a traded-away
  player's lineage children = what came back; terminates on drop or season-end),
  rendered as a tree with a **chain-adjusted "what you extracted" value**.
- **Full multi-hop chains, capped at season-end.** Purely informational — base
  per-trade grades and the OVR are untouched (so no double-counting).

### Veto-likelihood algorithm (new model)
- Per trade: **Veto Likelihood %** + band ("Looks fair / Lean veto / Collusion
  risk") + a one-line **per-team rationale**.
- **At-trade-time value** ("does this make sense *now*, given each team's roster +
  the players' *potential*") — preseason ADP + season-to-date trajectory =
  rest-of-season potential. **Not** hindsight VOR. (This is a distinct lens from
  the trade *grade*, which uses realized VOR.)
- **ADP-absent fallback (important):** League News is scoped to the most-recent
  season, which has **no vendored preseason ADP** (e.g. 2025). When ADP is missing,
  "potential" **falls back to season-to-date production + prior-season finish** —
  the algorithm must never depend on ADP being present, or veto is undefined for
  the exact season it targets.
- **Signals (weighted blend):** (1) value imbalance *(primary)*, (2) one-sided
  need — the fleeced team got nothing it needed → spikes; both fill needs → drops,
  (3) collusion pattern — repeat one-directional value flow between the same pair.
- **Calibrate:** normal trades <20%; lopsided + need-less + pattern-y >70%.

---

## Phase 4 — League News engine (snapshot, most-recent season)

- **Scope to the most-recent season**; older content stays in History.
- **Attribution on every item** (fix "draft bust: Malik Nabers #8" → name the
  manager who drafted him).
- **Clickable drill-downs:** each highlight → full **moment detail** (actual
  players/pick/trade/scores + who) **and top 3-5 contenders**. Add a top-N field
  per record category to the payload (currently winner-only).
- **In-feed trade rating:** recent-season trades appear as feed items with grade +
  veto % + a **hybrid trade-impact write-up** ("what this means for both teams").
- **Contextual waiver news:** "Team X picked up RB Y — they rank last in RB
  scoring, this helps" (positional-weakness aware).
- **Team strength/weakness stats:** positional-rank engine surfaced ("dead last in
  TEs, weakness = …").
- **Roster-aware waiver suggestions:** for each manager, best available free agents
  at their **weak positions**, ranked by **trailing ~3-4 week production**
  (need-weighted recent form), as-of the latest week of the most-recent season —
  the roster-specific recommendation fantasy apps don't do.

---

## Phase 5 — UI surfaces + nav consolidation

### GM profile redesign (`ManagerReport`, `/gms/[id]`)
- A real GM **profile**: manager's **fantasy-app icon**, **best finish**, three
  **highlight cards** (best waiver pickup, best draft pick, most impactful trade —
  where *most impactful trade* = the manager's single largest realized-VOR value
  swing in their favor), a **"View franchise history"** button → Franchise Hub,
  **remove the season aliases** (keep profile context).
- **Eye candy:** career **rating-trend** (stock-style line), **finish-history**
  timeline, **points-for vs league** distribution. (Skip the radar/pie.)

### Franchise Hub (`/managers/[key]`) — surface it in nav (no longer hidden)
Hosts the four deep features, alongside its existing career timeline/ledgers:
- **All-time lineup:** canonical slots (QB, RB, RB, WR, WR, TE, FLEX, K, DST),
  best **player-season per slot** by **raw season points**, **distinct players**,
  each must have been rostered by that manager that season.
- **Year-by-year rosters:** full-season **contributor ledger**, grouped **by
  position**, each player tagged with **source icon** (draft/trade/waiver/keeper) +
  **started/benched** counts + **weeks-on-roster tenure**; **filter/sort chips**:
  Top points / Most started / Most benched / Waiver. Reuse player chips + badges.
  Reachable by clicking a team in the **Season Hub standings** and from the
  **profile/Franchise Hub season timeline**.
- **Waiver breakdown** (drill-down target): waiver pickups ranked by **VOR value
  added** (gems), worst-drops as a secondary cut.
- **Draft career card** (from Phase 2).

### Other surfaces
- **Waiver value leader** (record book + home feed) becomes **clickable →
  navigate to that manager's waiver breakdown** (above). Build per-manager
  per-player waiver value (re-aggregated, VOR) — also feeds the roster view's
  waiver tag.
- **Season Hub draft board:** expand the steal/bust recap into a full **graded,
  ADP-annotated draft board**.
- **History ⊃ Seasons:** fold the Seasons grid into History (compact grid high,
  under the champion hero), **delete the Seasons nav item**, redirect
  `/seasons → /history`.
- **Rivalries ⊃ Head-to-Head:** make the Rivalries matrix canonical; **click a
  cell → pair drill-down** (absorb H2H's detail view); **retire/redirect
  `/head-to-head`** (kills its request-race + empty-state bugs).

---

## Definition of done

All 5 phases pass their verification gates; the demo league renders every new
surface correctly; QB-involved trades/waivers grade sanely (only ~elite QBs carry
strong value); the trade-grade distribution is bell-shaped; the OVR leaderboard
reflects V3; League News is scoped to the latest season with clickable,
attributed, written-up items; redundant nav (Seasons, Head-to-Head) is gone; and
web + API are deployed to Vercel.
