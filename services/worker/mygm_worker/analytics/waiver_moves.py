from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from mygm_worker.analytics.identity import load_team_seasons
from mygm_worker.analytics.json_tools import float_value, int_value, string_value
from mygm_worker.analytics.vor import build_vor_model, position_for_lookup_entry

if TYPE_CHECKING:
    from collections.abc import Iterable

    from mygm_worker.analytics.models import JsonObject, JsonValue
    from mygm_worker.analytics.reader import FixtureReader
    from mygm_worker.analytics.vor import VorModel

FAAB_UNAVAILABLE: Final = "FAAB context unavailable: bidAmount is always 0"


@dataclass(frozen=True, slots=True)
class _PlayerMove:
    player_id: int
    item_type: str
    from_team_id: int
    to_team_id: int


@dataclass(frozen=True, slots=True)
class _TeamContext:
    manager_key: str
    manager_name: str
    team_name: str


@dataclass(frozen=True, slots=True)
class _SeasonContext:
    final_week: int
    teams: dict[int, _TeamContext]


def waiver_move_rows(
    reader: FixtureReader, vor_model: VorModel | None = None
) -> tuple[dict[str, JsonValue], ...]:
    contexts = _season_contexts(reader)
    players = reader.player_lookup()
    model = vor_model if vor_model is not None else build_vor_model(reader)
    rows: list[JsonObject] = []
    for tx in reader.transaction_rows():
        tx_type = string_value(tx.get("type"))
        if tx_type not in {"WAIVER", "FREEAGENT"}:
            continue
        rows.append(_move_row(tx, contexts, players, model))
    return tuple(rows)


def manager_waiver_scores(rows: Iterable[dict[str, JsonValue]]) -> dict[str, JsonValue]:
    totals: dict[str, JsonObject] = {}
    for row in rows:
        if row.get("scoreEligible") is not True:
            continue
        manager_key = string_value(row.get("managerKey"))
        if not manager_key:
            continue
        total = totals.setdefault(
            manager_key,
            {
                "managerKey": manager_key,
                "managerName": string_value(row.get("managerName")),
                "eligibleMoves": 0,
                "addedRestOfSeasonPoints": 0.0,
                "droppedRestOfSeasonPoints": 0.0,
                "addedRestOfSeasonVor": 0.0,
                "droppedRestOfSeasonVor": 0.0,
                "netPoints": 0.0,
                "netVor": 0.0,
                "score": 0.0,
            },
        )
        total["eligibleMoves"] = int_value(total.get("eligibleMoves")) + 1
        added = float_value(total.get("addedRestOfSeasonPoints")) + float_value(
            row.get("addedRestOfSeasonPoints")
        )
        dropped = float_value(total.get("droppedRestOfSeasonPoints")) + float_value(
            row.get("droppedRestOfSeasonPoints")
        )
        added_vor = float_value(total.get("addedRestOfSeasonVor")) + float_value(
            row.get("addedRestOfSeasonVor")
        )
        dropped_vor = float_value(total.get("droppedRestOfSeasonVor")) + float_value(
            row.get("droppedRestOfSeasonVor")
        )
        net = float_value(total.get("netPoints")) + float_value(row.get("netPoints"))
        net_vor = float_value(total.get("netVor")) + float_value(row.get("netVor"))
        total["addedRestOfSeasonPoints"] = round(added, 4)
        total["droppedRestOfSeasonPoints"] = round(dropped, 4)
        total["addedRestOfSeasonVor"] = round(added_vor, 4)
        total["droppedRestOfSeasonVor"] = round(dropped_vor, 4)
        total["netPoints"] = round(net, 4)
        total["netVor"] = round(net_vor, 4)
        # Waiver value ranks on VOR (a streamed QB no longer out-scores a real RB pickup).
        total["score"] = round(net_vor, 4)
    return {key: totals[key] for key in sorted(totals)}


def _move_row(
    tx: JsonObject,
    contexts: dict[int, _SeasonContext],
    players: JsonObject,
    vor_model: VorModel,
) -> JsonObject:
    season = int_value(tx.get("_season"))
    week = int_value(tx.get("scoringPeriodId"))
    status = string_value(tx.get("status"), "UNKNOWN") or "UNKNOWN"
    team_id = int_value(tx.get("teamId"))
    context = contexts.get(season, _SeasonContext(final_week=week, teams={}))
    team = context.teams.get(
        team_id,
        _TeamContext(
            manager_key=f"unresolved:{season}:{team_id}",
            manager_name=f"Unresolved owner {team_id}",
            team_name=f"Team {team_id}",
        ),
    )
    transaction_date = int_value(tx.get("processDate")) or int_value(tx.get("date"))
    adds, drops = _moves(tx)
    exclusion_reason = ""
    if status != "EXECUTED":
        exclusion_reason = f"status:{status}"
    elif not adds:
        exclusion_reason = "executed_without_add"
    impact = _impact_totals(players, adds, drops, season, week, context.final_week, vor_model)
    if impact.points_available is False and exclusion_reason == "":
        exclusion_reason = "missing_player_points"
    score_eligible = exclusion_reason == ""
    added_points = impact.added_total if score_eligible else 0.0
    dropped_points = impact.dropped_total if score_eligible else 0.0
    added_vor = impact.added_vor if score_eligible else 0.0
    dropped_vor = impact.dropped_vor if score_eligible else 0.0
    net_points = round(added_points - dropped_points, 4) if score_eligible else 0.0
    net_vor = round(added_vor - dropped_vor, 4) if score_eligible else 0.0
    return {
        "season": season,
        "week": week,
        "transactionDateMs": transaction_date,
        "managerKey": team.manager_key,
        "managerName": team.manager_name,
        "teamId": team_id,
        "teamName": team.team_name,
        "transactionType": string_value(tx.get("type")),
        "status": status,
        "addedPlayers": (
            impact.added_players if score_eligible else [_player_row(move) for move in adds]
        ),
        "droppedPlayers": (
            impact.dropped_players if score_eligible else [_player_row(move) for move in drops]
        ),
        "addedRestOfSeasonPoints": added_points,
        "droppedRestOfSeasonPoints": dropped_points,
        "addedRestOfSeasonVor": added_vor,
        "droppedRestOfSeasonVor": dropped_vor,
        "dropRegret": dropped_points,
        "netPoints": net_points,
        "netVor": net_vor,
        "scoreEligible": score_eligible,
        "faabCaveat": (
            FAAB_UNAVAILABLE if int_value(tx.get("bidAmount")) == 0 else "FAAB bidAmount present"
        ),
        "exclusionReason": exclusion_reason,
        "sourceTransactionId": string_value(tx.get("id")),
        "sourceFile": string_value(tx.get("_source_file")),
        "sourceIndex": int_value(tx.get("_source_index")),
        "sortKeys": {
            "bestPickup": added_points,
            "worstDrop": dropped_points,
            "netPoints": net_points,
        },
    }


def _season_contexts(reader: FixtureReader) -> dict[int, _SeasonContext]:
    managers, team_seasons = load_team_seasons(reader)
    final_weeks = {season.season: season.final_week for season in reader.seasons()}
    contexts: dict[int, _SeasonContext] = {}
    for team_season in team_seasons:
        season_context = contexts.setdefault(
            team_season.season,
            _SeasonContext(final_week=final_weeks[team_season.season], teams={}),
        )
        season_context.teams[team_season.team_id] = _TeamContext(
            manager_key=team_season.manager_key,
            manager_name=managers[team_season.manager_key].display_name,
            team_name=team_season.team_name,
        )
    return contexts


def _moves(tx: JsonObject) -> tuple[tuple[_PlayerMove, ...], tuple[_PlayerMove, ...]]:
    moves: defaultdict[str, list[_PlayerMove]] = defaultdict(list)
    items = tx.get("items")
    if not isinstance(items, list):
        return (), ()
    for item in items:
        if isinstance(item, dict):
            item_type = string_value(item.get("type"))
            if item_type in {"ADD", "DROP"}:
                moves[item_type].append(
                    _PlayerMove(
                        player_id=int_value(item.get("playerId")),
                        item_type=item_type,
                        from_team_id=int_value(item.get("fromTeamId")),
                        to_team_id=int_value(item.get("toTeamId")),
                    )
                )
    return tuple(moves["ADD"]), tuple(moves["DROP"])


@dataclass(frozen=True, slots=True)
class _PlayerImpact:
    row: JsonObject
    points: float
    vor: float
    available: bool


@dataclass(frozen=True, slots=True)
class _ImpactTotals:
    added_players: list[JsonValue]
    dropped_players: list[JsonValue]
    added_total: float
    dropped_total: float
    added_vor: float
    dropped_vor: float
    points_available: bool


def _impact_totals(
    players: JsonObject,
    adds: tuple[_PlayerMove, ...],
    drops: tuple[_PlayerMove, ...],
    season: int,
    start_week: int,
    final_week: int,
    vor_model: VorModel,
) -> _ImpactTotals:
    added = [_player_impact(players, m, season, start_week, final_week, vor_model) for m in adds]
    dropped = [_player_impact(players, m, season, start_week, final_week, vor_model) for m in drops]
    return _ImpactTotals(
        added_players=[impact.row for impact in added],
        dropped_players=[impact.row for impact in dropped],
        added_total=round(sum(impact.points for impact in added), 4),
        dropped_total=round(sum(impact.points for impact in dropped), 4),
        added_vor=round(sum(impact.vor for impact in added), 4),
        dropped_vor=round(sum(impact.vor for impact in dropped), 4),
        points_available=all(impact.available for impact in [*added, *dropped]),
    )


def _player_impact(
    players: JsonObject,
    move: _PlayerMove,
    season: int,
    start_week: int,
    final_week: int,
    vor_model: VorModel,
) -> _PlayerImpact:
    player = players.get(str(move.player_id))
    if not isinstance(player, dict):
        return _PlayerImpact(
            row=_player_row(move, "", 0.0, 0.0, points_available=False),
            points=0.0,
            vor=0.0,
            available=False,
        )
    weekly = player.get("weekly_points")
    season_points = weekly.get(str(season)) if isinstance(weekly, dict) else None
    if not isinstance(season_points, dict):
        return _PlayerImpact(
            row=_player_row(
                move, string_value(player.get("name")), 0.0, 0.0, points_available=False
            ),
            points=0.0,
            vor=0.0,
            available=False,
        )
    position = position_for_lookup_entry(player)
    total = 0.0
    windowed: dict[str, JsonValue] = {}
    for week_text, points in season_points.items():
        week = int_value(week_text)
        if start_week <= week <= final_week:
            total += float_value(points)
            windowed[week_text] = points
    rounded = round(total, 4)
    vor, _ = vor_model.value_for_weeks(season, position, windowed)
    return _PlayerImpact(
        row=_player_row(
            move, string_value(player.get("name")), rounded, vor, points_available=True
        ),
        points=rounded,
        vor=vor,
        available=True,
    )


def _player_row(
    move: _PlayerMove,
    name: str = "",
    points: float = 0.0,
    vor: float = 0.0,
    *,
    points_available: bool = False,
) -> JsonObject:
    return {
        "playerId": move.player_id,
        "name": name or f"Unknown Player {move.player_id}",
        "itemType": move.item_type,
        "fromTeamId": move.from_team_id,
        "toTeamId": move.to_team_id,
        "restOfSeasonPoints": points,
        "restOfSeasonVor": vor,
        "pointsAvailable": points_available,
    }


def waiver_superlatives(
    rows: Iterable[dict[str, JsonValue]],
    *,
    names: dict[str, str],
) -> dict[int, JsonObject]:
    """Per-season waiver-wire award cards built from the eligible move rows.

    Four cards per season: the best pickup (most rest-of-season points added), the worst
    drop (most points let walk), the savviest wire value (most net VOR), and the most
    active manager (most eligible moves). Each card names the manager and the player or
    move count behind the headline value.
    """
    by_season: defaultdict[int, list[JsonObject]] = defaultdict(list)
    for row in rows:
        if row.get("scoreEligible") is not True:
            continue
        by_season[int_value(row.get("season"))].append(dict(row))
    result: dict[int, JsonObject] = {}
    for season in sorted(by_season):
        season_rows = by_season[season]
        result[season] = {
            "season": season,
            "bestPickup": _best_row_card(
                season_rows, names, metric="addedRestOfSeasonPoints", players_key="addedPlayers"
            ),
            "worstDrop": _best_row_card(
                season_rows, names, metric="droppedRestOfSeasonPoints", players_key="droppedPlayers"
            ),
            "bestWireValue": _best_row_card(
                season_rows, names, metric="netVor", players_key="addedPlayers"
            ),
            "mostActive": _most_active_card(season_rows, names),
        }
    return result


def _best_row_card(
    rows: list[JsonObject],
    names: dict[str, str],
    *,
    metric: str,
    players_key: str,
) -> JsonValue:
    best: JsonObject | None = None
    best_value = 0.0
    for row in rows:
        value = float_value(row.get(metric))
        if value > best_value:
            best_value = value
            best = row
    if best is None:
        return None
    player = _headline_player(best.get(players_key))
    return _superlative_card(
        best,
        names,
        value=best_value,
        player=string_value(player.get("name")),
        vor=float_value(best.get("netVor")),
    )


def _most_active_card(rows: list[JsonObject], names: dict[str, str]) -> JsonValue:
    counts: defaultdict[str, int] = defaultdict(int)
    for row in rows:
        counts[string_value(row.get("managerKey"))] += 1
    if not counts:
        return None
    manager_key = sorted(counts, key=lambda key: (-counts[key], key))[0]
    season = int_value(rows[0].get("season")) if rows else 0
    return {
        "managerKey": manager_key,
        "displayName": names.get(manager_key, manager_key),
        "value": counts[manager_key],
        "player": "",
        "count": counts[manager_key],
        "season": season,
        "week": 0,
        "detail": f"{counts[manager_key]} eligible moves",
    }


def _superlative_card(
    row: JsonObject,
    names: dict[str, str],
    *,
    value: float,
    player: str,
    vor: float,
) -> JsonObject:
    manager_key = string_value(row.get("managerKey"))
    display_name = names.get(manager_key) or string_value(row.get("managerName")) or manager_key
    return {
        "managerKey": manager_key,
        "displayName": display_name,
        "value": round(value, 4),
        "player": player,
        "count": 0,
        "season": int_value(row.get("season")),
        "week": int_value(row.get("week")),
        "netVor": round(vor, 4),
        "detail": string_value(row.get("transactionType")),
    }


def _headline_player(players: JsonValue) -> JsonObject:
    best: JsonObject | None = None
    best_points = float("-inf")
    if isinstance(players, list):
        for item in players:
            if isinstance(item, dict):
                points = float_value(item.get("restOfSeasonPoints"))
                if points > best_points:
                    best_points = points
                    best = item
    return best if best is not None else {}
