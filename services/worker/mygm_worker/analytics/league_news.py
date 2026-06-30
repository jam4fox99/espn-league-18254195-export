"""League News engine — a dynamic, attributed feed scoped to the most-recent season.

Everything older lives in History; this is "what's happening now" built on the latest
season in the snapshot, architected so that running the same pipeline on fresher data
is all "live" would ever require.

Prose is hybrid: every fact comes from a deterministic template (always on, fully
testable, never hallucinates); an LLM only polishes phrasing when ``MYGM_NEWS_LLM`` +
``ANTHROPIC_API_KEY`` are present — the same opt-in pattern as manager archetypes.

The feed covers, all attributed and each with a clickable drill-down (+ top contenders
where it makes sense): in-feed trade ratings (grade + veto + a both-teams write-up),
context-aware waiver pickups, the season's draft steal/bust, record performances, and a
champion recap. Alongside the feed it surfaces per-team positional strength/weakness and
roster-aware waiver suggestions (best available free agents at each team's weak spots,
ranked by recent form).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, cast

from mygm_worker.analytics.json_tools import (
    as_array,
    as_object,
    float_value,
    int_value,
    object_field,
    read_json,
    string_value,
)
from mygm_worker.analytics.roster_fit import FIT_POSITIONS
from mygm_worker.analytics.vor import position_for_lookup_entry

if TYPE_CHECKING:
    from collections.abc import Sequence
    from http.client import HTTPResponse

    from mygm_worker.analytics.draft import SeasonDraft
    from mygm_worker.analytics.models import JsonObject, JsonValue, TeamSeason
    from mygm_worker.analytics.reader import FixtureReader
    from mygm_worker.analytics.roster_fit import FitIndex
    from mygm_worker.analytics.trade_grades import TradeGrade
    from mygm_worker.analytics.veto import VetoResult
    from mygm_worker.analytics.vor import VorModel

_TOP_TRADES: Final = 6
_TOP_WAIVERS: Final = 6
_TOP_PERFORMANCES: Final = 5
_TRAILING_WEEKS: Final = 3
_SUGGESTIONS_PER_MANAGER: Final = 3
_WEAKNESS_NEED: Final = 0.5
_NON_STARTING_SLOTS: Final = frozenset({20, 21})


@dataclass(frozen=True, slots=True)
class NewsContext:
    season: int
    final_week: int
    reader: FixtureReader
    team_seasons: list[TeamSeason]
    names: dict[str, str]
    team_lookup: dict[tuple[int, int], str]
    graded_pairs: list[tuple[JsonObject, TradeGrade]]
    veto_results: dict[str, VetoResult]
    waiver_rows: list[JsonObject]
    drafts: Sequence[SeasonDraft]
    standings: JsonObject | None
    fit_index: FitIndex
    vor_model: VorModel
    position_by_player: dict[int, str]


def build_league_news(context: NewsContext) -> JsonObject:
    items: list[JsonValue] = []
    items.extend(_champion_item(context))
    items.extend(_trade_items(context))
    items.extend(_waiver_items(context))
    items.extend(_draft_items(context))
    items.extend(_performance_items(context))
    return {
        "season": context.season,
        "items": items,
        "teamStrength": _team_strength(context),
        "waiverSuggestions": _waiver_suggestions(context),
    }


# ------------------------------------------------------------------ feed items


def _champion_item(context: NewsContext) -> list[JsonValue]:
    standings = context.standings
    if not isinstance(standings, dict):
        return []
    champion = standings.get("champion")
    if not isinstance(champion, dict):
        return []
    name = string_value(champion.get("displayName"))
    runner_up = standings.get("runnerUp")
    runner_name = string_value(runner_up.get("displayName")) if isinstance(runner_up, dict) else ""
    detail = f"{name} won the {context.season} title."
    if runner_name:
        detail = f"{name} won the {context.season} title over {runner_name}."
    return [
        {
            "id": f"news:{context.season}:champion",
            "type": "champion",
            "headline": f"{name} are {context.season} champions",
            "detail": detail,
            "season": context.season,
            "managerKey": string_value(champion.get("managerKey")),
            "displayName": name,
            "drillDown": {"finalStandings": standings.get("finalStandings")},
        }
    ]


def _trade_items(context: NewsContext) -> list[JsonValue]:
    season_pairs = [
        (row, grade)
        for row, grade in context.graded_pairs
        if grade.season == context.season and len(grade.sides) == 2
    ]
    season_pairs.sort(key=lambda pair: max(side.composite for side in pair[1].sides), reverse=True)
    items: list[JsonValue] = []
    for row, grade in season_pairs[:_TOP_TRADES]:
        veto = context.veto_results.get(grade.trade_id)
        items.append(
            {
                "id": f"news:{context.season}:trade:{grade.trade_id}",
                "type": "trade",
                "headline": _trade_headline(grade, context.names),
                "detail": _trade_writeup(row, grade, veto, context.names),
                "season": context.season,
                "managerKeys": [side.manager_key for side in grade.sides],
                "veto": None if veto is None else {"percent": veto.percent, "band": veto.band},
                "grades": {side.manager_key: side.grade for side in grade.sides},
                "drillDown": {"tradeId": grade.trade_id, "sides": row.get("sides")},
            }
        )
    return items


def _waiver_items(context: NewsContext) -> list[JsonValue]:
    rows = [
        row
        for row in context.waiver_rows
        if int_value(row.get("season")) == context.season
        and row.get("scoreEligible") is True
        and float_value(row.get("addedRestOfSeasonVor")) > 0
    ]
    rows.sort(key=lambda row: float_value(row.get("addedRestOfSeasonVor")), reverse=True)
    items: list[JsonValue] = []
    for row in rows[:_TOP_WAIVERS]:
        manager_key = string_value(row.get("managerKey"))
        added = _added_player(row)
        if added is None:
            continue
        position = string_value(added.get("position")) or context.position_by_player.get(
            int_value(added.get("playerId")), ""
        )
        tx_id = string_value(row.get("sourceTransactionId"))
        items.append(
            {
                "id": f"news:{context.season}:waiver:{tx_id}",
                "type": "waiver",
                "headline": (
                    f"{context.names.get(manager_key, manager_key)} added "
                    f"{string_value(added.get('name'), 'a free agent')}"
                ),
                "detail": _waiver_context(context, manager_key, position, row),
                "season": context.season,
                "managerKey": manager_key,
                "displayName": context.names.get(manager_key, manager_key),
                "drillDown": {"moveId": row.get("moveId"), "addedPlayers": row.get("addedPlayers")},
            }
        )
    return items


def _draft_items(context: NewsContext) -> list[JsonValue]:
    draft = next((draft for draft in context.drafts if draft.season == context.season), None)
    if draft is None:
        return []
    items: list[JsonValue] = []
    if draft.best_steal is not None:
        pick = draft.best_steal
        items.append(
            {
                "id": f"news:{context.season}:draft-steal",
                "type": "draftSteal",
                "headline": f"Draft steal: {pick.player_name}",
                "detail": (
                    f"{pick.display_name} stole {pick.player_name} at pick "
                    f"#{pick.overall_pick} — finished #{pick.points_rank} in points "
                    f"(+{pick.surplus:.0f} VOR over the slot)."
                ),
                "season": context.season,
                "managerKey": pick.manager_key,
                "displayName": pick.display_name,
                "drillDown": {"playerId": pick.player_id, "overallPick": pick.overall_pick},
            }
        )
    if draft.biggest_bust is not None:
        pick = draft.biggest_bust
        items.append(
            {
                "id": f"news:{context.season}:draft-bust",
                "type": "draftBust",
                "headline": f"Draft bust: {pick.player_name}",
                "detail": (
                    f"{pick.display_name} spent pick #{pick.overall_pick} on "
                    f"{pick.player_name}, who finished #{pick.points_rank} in points "
                    f"({pick.surplus:.0f} VOR vs the slot)."
                ),
                "season": context.season,
                "managerKey": pick.manager_key,
                "displayName": pick.display_name,
                "drillDown": {"playerId": pick.player_id, "overallPick": pick.overall_pick},
            }
        )
    return items


def _performance_items(context: NewsContext) -> list[JsonValue]:
    scores = sorted(
        (
            (week, team_id, score)
            for season, week, team_id, score in context.reader.weekly_scores()
            if season == context.season
        ),
        key=lambda row: -row[2],
    )
    if not scores:
        return []
    contenders: list[JsonValue] = [
        {
            "week": week,
            "managerKey": context.team_lookup.get((context.season, team_id)),
            "displayName": context.names.get(
                context.team_lookup.get((context.season, team_id), ""), "Unknown"
            ),
            "points": round(score, 4),
        }
        for week, team_id, score in scores[:_TOP_PERFORMANCES]
    ]
    top_week, top_team, top_score = scores[0]
    manager_key = context.team_lookup.get((context.season, top_team), "")
    return [
        {
            "id": f"news:{context.season}:top-week",
            "type": "performance",
            "headline": f"Top week: {round(top_score, 1)} points",
            "detail": (
                f"{context.names.get(manager_key, manager_key)} dropped "
                f"{round(top_score, 1)} in week {top_week} — the season's high-water mark."
            ),
            "season": context.season,
            "managerKey": manager_key,
            "displayName": context.names.get(manager_key, manager_key),
            "drillDown": {"week": top_week},
            "contenders": contenders,
        }
    ]


# ------------------------------------------------------- strength + suggestions


def _team_strength(context: NewsContext) -> list[JsonValue]:
    rows: list[JsonValue] = []
    managers = sorted(
        {
            row.manager_key
            for row in context.team_seasons
            if row.season == context.season and not row.manager_key.startswith("unresolved:")
        }
    )
    for manager_key in managers:
        needs = {
            position: context.fit_index.need(
                context.season, manager_key, context.final_week, position
            )
            for position in sorted(FIT_POSITIONS)
        }
        strengths = {
            position: context.fit_index.fit_value(
                context.season, manager_key, context.final_week, position
            )
            for position in sorted(FIT_POSITIONS)
        }
        weakest = max(needs, key=lambda position: needs[position])
        strongest = max(strengths, key=lambda position: strengths[position])
        needs_json: dict[str, JsonValue] = {
            position: round(value, 4) for position, value in needs.items()
        }
        rows.append(
            {
                "managerKey": manager_key,
                "displayName": context.names.get(manager_key, manager_key),
                "weakestPosition": weakest if needs[weakest] >= _WEAKNESS_NEED else None,
                "strongestPosition": strongest,
                "needs": needs_json,
            }
        )
    return rows


def _waiver_suggestions(context: NewsContext) -> list[JsonValue]:
    rostered = _rostered_at(context.reader, context.season, context.final_week)
    available = _available_free_agents(context, rostered)
    rows: list[JsonValue] = []
    managers = sorted(
        {
            row.manager_key
            for row in context.team_seasons
            if row.season == context.season and not row.manager_key.startswith("unresolved:")
        }
    )
    for manager_key in managers:
        weak = [
            position
            for position in sorted(FIT_POSITIONS)
            if context.fit_index.need(context.season, manager_key, context.final_week, position)
            >= _WEAKNESS_NEED
        ]
        suggestions: list[JsonValue] = [
            {
                "position": position,
                "playerId": player[0],
                "name": player[1],
                "trailingPoints": round(player[2], 4),
            }
            for position in weak
            for player in available.get(position, [])[:_SUGGESTIONS_PER_MANAGER]
        ]
        if suggestions:
            weak_json: list[JsonValue] = [position for position in weak]  # noqa: C416
            rows.append(
                {
                    "managerKey": manager_key,
                    "displayName": context.names.get(manager_key, manager_key),
                    "weakPositions": weak_json,
                    "suggestions": suggestions,
                }
            )
    return rows


def _available_free_agents(
    context: NewsContext,
    rostered: set[int],
) -> dict[str, list[tuple[int, str, float]]]:
    by_position: dict[str, list[tuple[int, str, float]]] = {
        position: [] for position in FIT_POSITIONS
    }
    low = context.final_week - _TRAILING_WEEKS + 1
    for player_id_text, player in context.reader.player_lookup().items():
        if not isinstance(player, dict):
            continue
        player_id = int_value(player_id_text)
        if player_id in rostered:
            continue
        position = position_for_lookup_entry(player)
        if position not in FIT_POSITIONS:
            continue
        weekly = player.get("weekly_points")
        season_weeks = weekly.get(str(context.season)) if isinstance(weekly, dict) else None
        if not isinstance(season_weeks, dict):
            continue
        trailing = sum(
            float_value(points)
            for week_text, points in season_weeks.items()
            if low <= int_value(week_text) <= context.final_week
        )
        if trailing > 0:
            by_position[position].append((player_id, string_value(player.get("name")), trailing))
    for entries in by_position.values():
        entries.sort(key=lambda item: -item[2])
    return by_position


def _rostered_at(reader: FixtureReader, season: int, week: int) -> set[int]:
    rostered: set[int] = set()
    week_path = reader.root / f"season_{season}" / "box_scores" / f"week_{week:02d}.json"
    if not week_path.exists():
        return rostered
    data = object_field(as_object(read_json(week_path), str(week_path)), "data")
    schedule = data.get("schedule")
    if not isinstance(schedule, list):
        return rostered
    for matchup in schedule:
        if not isinstance(matchup, dict):
            continue
        for side_name in ("home", "away"):
            side = matchup.get(side_name)
            if isinstance(side, dict):
                rostered.update(_roster_ids(side))
    return rostered


def _roster_ids(side: JsonObject) -> set[int]:
    roster = side.get("rosterForCurrentScoringPeriod")
    entries = roster.get("entries") if isinstance(roster, dict) else None
    ids: set[int] = set()
    if not isinstance(entries, list):
        return ids
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        pool = entry.get("playerPoolEntry")
        player = pool.get("player") if isinstance(pool, dict) else None
        if isinstance(player, dict):
            ids.add(int_value(player.get("id")))
    return ids


# ------------------------------------------------------------------ prose


def _trade_headline(grade: TradeGrade, names: dict[str, str]) -> str:
    winner = grade.winner_manager_key
    if winner is None:
        managers = " & ".join(names.get(side.manager_key, side.manager_key) for side in grade.sides)
        return f"Even swap: {managers}"
    winner_name = names.get(winner, winner)
    other = next((side for side in grade.sides if side.manager_key != winner), None)
    other_name = names.get(other.manager_key, other.manager_key) if other else "their partner"
    return f"{winner_name} fleece {other_name}" if grade.value_gap > 60 else (
        f"{winner_name} edge {other_name}"
    )


def _trade_writeup(
    row: JsonObject,
    grade: TradeGrade,
    veto: VetoResult | None,
    names: dict[str, str],
) -> str:
    parts: list[str] = []
    for side in grade.sides:
        name = names.get(side.manager_key, side.manager_key)
        assets = _side_assets(row, side.team_id)
        need = (
            f" filling a need at {', '.join(side.needs_filled)}" if side.needs_filled else ""
        )
        parts.append(f"{name} ({side.grade}) got {assets}{need}")
    base = "; ".join(parts) + "."
    if veto is not None:
        base = f"{base} Veto risk {veto.percent:.0f}% — {veto.band.lower()}."
    return _polish(base, {"type": "trade", "tradeId": grade.trade_id})


def _waiver_context(
    context: NewsContext,
    manager_key: str,
    position: str,
    row: JsonObject,
) -> str:
    added = float_value(row.get("addedRestOfSeasonVor"))
    name = context.names.get(manager_key, manager_key)
    if position in FIT_POSITIONS:
        week = int_value(row.get("week"))
        need = context.fit_index.need(context.season, manager_key, week, position)
        if need >= _WEAKNESS_NEED:
            detail = (
                f"{name} ranked among the league's worst at {position} — "
                f"this pickup ({added:+.0f} VOR) helps where it hurts."
            )
            return _polish(detail, {"type": "waiver"})
    return _polish(
        f"{name}'s pickup added {added:+.0f} VOR over the rest of the season.",
        {"type": "waiver"},
    )


def _side_assets(row: JsonObject, team_id: int) -> str:
    for side in as_array(row.get("sides"), "sides"):
        if not isinstance(side, dict) or int_value(side.get("teamId")) != team_id:
            continue
        assets = [
            string_value(asset.get("name"), "a player")
            for asset in as_array(side.get("receivedAssets"), "receivedAssets")
            if isinstance(asset, dict)
        ]
        if assets:
            return ", ".join(assets[:4])
    return "assets"


def _added_player(row: JsonObject) -> JsonObject | None:
    best: JsonObject | None = None
    best_value = float("-inf")
    for player in as_array(row.get("addedPlayers"), "addedPlayers"):
        if isinstance(player, dict) and float_value(player.get("restOfSeasonVor")) > best_value:
            best = player
            best_value = float_value(player.get("restOfSeasonVor"))
    return best


# ------------------------------------------------------------- optional LLM polish


def _llm_enabled() -> bool:
    return os.environ.get("MYGM_NEWS_LLM", "").strip().lower() in {"1", "true", "yes"}


def _polish(text: str, context: dict[str, str]) -> str:
    """Return LLM-polished prose when MYGM_NEWS_LLM + a key are present, else the template."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or not _llm_enabled():
        return text
    model = os.environ.get("MYGM_NEWS_MODEL", "claude-haiku-4-5")
    prompt = (
        "Rewrite this fantasy-football news line in a crisp beat-writer voice. Keep every "
        "fact, name, and number exactly; max 30 words; no preamble, no dollar signs. "
        f"Context: {json.dumps(context)}. Line: {text}"
    )
    body = json.dumps(
        {"model": model, "max_tokens": 90, "messages": [{"role": "user", "content": prompt}]}
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        response = cast("HTTPResponse", urllib.request.urlopen(request, timeout=30))
        try:
            decoded = response.read().decode("utf-8")
        finally:
            response.close()
        payload = as_object(cast("JsonValue", json.loads(decoded)), "llm")
        blocks = payload.get("content")
        polished = " ".join(
            string_value(block.get("text"))
            for block in (blocks if isinstance(blocks, list) else [])
            if isinstance(block, dict)
        ).strip()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return text
    return polished or text
