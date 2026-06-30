"""Asset trade-tree / journey — a purely informational lineage view.

Click a trade and trace each acquired asset forward through that manager's dated
transaction timeline: a player traded away branches into whatever came back; the chain
terminates on a drop or at season end. Each node carries the VOR the player produced
during the manager's tenure, and the root reports a chain-adjusted "what you
ultimately extracted" value (the VOR pooled across the leaves of the tree).

This view never feeds the per-trade grade or the OVR — it would double-count — so it
lives entirely outside the grading path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from mygm_worker.analytics.json_tools import as_array, int_value, string_value

if TYPE_CHECKING:
    from mygm_worker.analytics.models import JsonObject, JsonValue
    from mygm_worker.analytics.reader import FixtureReader
    from mygm_worker.analytics.vor import VorModel

_MAX_DEPTH: Final = 8  # chains are capped well below this in practice; a runaway guard.


@dataclass(frozen=True, slots=True)
class _Move:
    week: int
    kind: str  # "acquired" | "traded_away" | "dropped"
    # For a trade-away, the players that came back in the same deal.
    returned: tuple[tuple[int, str], ...] = ()


@dataclass(slots=True)
class _Timeline:
    # (season, manager_key, player_id) -> chronological moves affecting that player.
    moves: dict[tuple[int, str, int], list[_Move]] = field(default_factory=dict)
    # (season, manager_key, player_id) -> end week of the season (tenure cap).
    final_week: dict[int, int] = field(default_factory=dict)


def trade_trees(
    trade_rows: list[JsonObject],
    waiver_rows: list[JsonObject],
    *,
    reader: FixtureReader,
    vor_model: VorModel,
    position_by_player: dict[int, str],
    team_lookup: dict[tuple[int, int], str],
) -> JsonObject:
    """Build a lineage tree for every score-eligible trade, keyed by trade id."""
    final_weeks = {season.season: season.final_week for season in reader.seasons()}
    players = reader.player_lookup()
    timeline = _build_timeline(trade_rows, waiver_rows, team_lookup)
    trees: JsonObject = {}
    for row in trade_rows:
        if row.get("scoreEligible") is not True:
            continue
        trade_id = string_value(row.get("tradeId"))
        season = int_value(row.get("season"))
        week = int_value(row.get("week"))
        final_week = final_weeks.get(season, 17)
        branches: list[JsonValue] = []
        extracted = 0.0
        for side in as_array(row.get("sides"), "sides"):
            if not isinstance(side, dict):
                continue
            manager_key = team_lookup.get((season, int_value(side.get("teamId"))))
            if manager_key is None:
                continue
            for asset in as_array(side.get("receivedAssets"), "receivedAssets"):
                if not isinstance(asset, dict):
                    continue
                node, leaf_vor = _trace(
                    int_value(asset.get("playerId")),
                    string_value(asset.get("name"), "Unknown Player"),
                    season,
                    week,
                    manager_key,
                    timeline,
                    players,
                    vor_model,
                    position_by_player,
                    final_week,
                    depth=0,
                )
                extracted += leaf_vor
                branches.append({"managerKey": manager_key, **node})
        trees[trade_id] = {
            "tradeId": trade_id,
            "season": season,
            "branches": branches,
            "extractedVor": round(extracted, 4),
        }
    return trees


def _trace(
    player_id: int,
    name: str,
    season: int,
    acquired_week: int,
    manager_key: str,
    timeline: _Timeline,
    players: JsonObject,
    vor_model: VorModel,
    position_by_player: dict[int, str],
    final_week: int,
    *,
    depth: int,
) -> tuple[JsonObject, float]:
    moves = timeline.moves.get((season, manager_key, player_id), [])
    next_move = _next_move_after(moves, acquired_week)
    end_week = next_move.week if next_move is not None else final_week
    tenure_vor = _player_vor(
        players, player_id, season, acquired_week, end_week, vor_model, position_by_player
    )
    node: JsonObject = {
        "playerId": player_id,
        "name": name,
        "acquiredWeek": acquired_week,
        "tenureVor": tenure_vor,
    }
    if next_move is None or depth >= _MAX_DEPTH:
        node["outcome"] = "held"
        return node, tenure_vor
    if next_move.kind == "dropped":
        node["outcome"] = "dropped"
        node["exitWeek"] = next_move.week
        return node, 0.0  # dropped chains extract nothing further.
    # Traded away: the players that came back are this node's lineage children.
    node["outcome"] = "traded_away"
    node["exitWeek"] = next_move.week
    children: list[JsonValue] = []
    child_vor = 0.0
    for child_id, child_name in next_move.returned:
        child_node, leaf = _trace(
            child_id,
            child_name,
            season,
            next_move.week,
            manager_key,
            timeline,
            players,
            vor_model,
            position_by_player,
            final_week,
            depth=depth + 1,
        )
        children.append(child_node)
        child_vor += leaf
    node["children"] = children
    return node, child_vor


def _build_timeline(
    trade_rows: list[JsonObject],
    waiver_rows: list[JsonObject],
    team_lookup: dict[tuple[int, int], str],
) -> _Timeline:
    timeline = _Timeline()
    for row in trade_rows:
        if row.get("scoreEligible") is True:
            _absorb_trade(timeline, row, team_lookup)
    for row in waiver_rows:
        season = int_value(row.get("season"))
        week = int_value(row.get("week"))
        manager_key = string_value(row.get("managerKey"))
        if not manager_key:
            continue
        for dropped in as_array(row.get("droppedPlayers"), "droppedPlayers"):
            if isinstance(dropped, dict):
                _add_move(
                    timeline, season, manager_key, int_value(dropped.get("playerId")),
                    _Move(week, "dropped"),
                )
    return timeline


def _absorb_trade(
    timeline: _Timeline,
    row: JsonObject,
    team_lookup: dict[tuple[int, int], str],
) -> None:
    season = int_value(row.get("season"))
    week = int_value(row.get("week"))
    sides = [side for side in as_array(row.get("sides"), "sides") if isinstance(side, dict)]
    for side in sides:
        manager_key = team_lookup.get((season, int_value(side.get("teamId"))))
        if manager_key is None:
            continue
        received = _asset_pairs(side)
        given = [pair for other in sides if other is not side for pair in _asset_pairs(other)]
        for player_id, _name in received:
            _add_move(timeline, season, manager_key, player_id, _Move(week, "acquired"))
        for player_id, _name in given:
            _add_move(
                timeline, season, manager_key, player_id,
                _Move(week, "traded_away", tuple(received)),
            )


def _asset_pairs(side: JsonObject) -> list[tuple[int, str]]:
    return [
        (int_value(asset.get("playerId")), string_value(asset.get("name"), "Unknown Player"))
        for asset in as_array(side.get("receivedAssets"), "receivedAssets")
        if isinstance(asset, dict)
    ]


def _add_move(
    timeline: _Timeline, season: int, manager_key: str, player_id: int, move: _Move
) -> None:
    timeline.moves.setdefault((season, manager_key, player_id), []).append(move)


def _next_move_after(moves: list[_Move], week: int) -> _Move | None:
    later = sorted(
        (move for move in moves if move.week > week and move.kind != "acquired"),
        key=lambda move: move.week,
    )
    return later[0] if later else None


def _player_vor(
    players: JsonObject,
    player_id: int,
    season: int,
    start_week: int,
    end_week: int,
    vor_model: VorModel,
    position_by_player: dict[int, str],
) -> float:
    player = players.get(str(player_id))
    weekly = player.get("weekly_points") if isinstance(player, dict) else None
    season_weeks = weekly.get(str(season)) if isinstance(weekly, dict) else None
    if not isinstance(season_weeks, dict):
        return 0.0
    return vor_model.window_value(
        season, position_by_player.get(player_id, ""), season_weeks, start_week, end_week
    )
