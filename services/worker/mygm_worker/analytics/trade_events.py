from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


class TradeGradeRowReader(Protocol):
    def trade_grade_rows(self) -> Sequence[JsonObject]: ...


def trade_event_rows(reader: TradeGradeRowReader) -> tuple[JsonObject, ...]:
    rows = (_event_row(row) for row in reader.trade_grade_rows())
    return tuple(sorted(rows, key=_sort_key))


def filter_trade_events(
    rows: Sequence[JsonObject],
    *,
    season: int | None = None,
    manager_key: str | None = None,
    mine_only: bool = False,
    sort: Literal["chronological", "best"] = "chronological",
) -> tuple[JsonObject, ...]:
    filtered = [
        row
        for row in rows
        if _matches_season(row, season) and _matches_manager(row, manager_key, mine_only)
    ]
    if sort == "best":
        return tuple(sorted(filtered, key=_best_sort_key))
    return tuple(sorted(filtered, key=_sort_key))


def _event_row(row: JsonObject) -> JsonObject:
    source_trade_id = _text(row.get("trade_id")) or _fallback_source_trade_id(row)
    net_points = _float_or_none(row.get("net_difference"))
    sides = _sides(row, net_points)
    objective_winner = _winner_json(sides)
    ungraded_reason = _text(row.get("ungraded_reason"))
    score_eligible = net_points is not None and objective_winner is not None
    return {
        "tradeId": _stable_trade_id(row, source_trade_id),
        "sourceTradeId": source_trade_id,
        "season": _int_or_none(row.get("season")),
        "week": _int_or_none(row.get("week")),
        "date": _text(row.get("trade_date_utc")),
        "managerKeys": _manager_keys(sides),
        "teamIds": _team_ids(sides),
        "sides": sides,
        "postTradePoints": {
            "teamA": _side_field_float(sides, "teamA", "postTradePoints"),
            "teamB": _side_field_float(sides, "teamB", "postTradePoints"),
        },
        "scoreWindow": {
            "startWeek": _int_or_none(row.get("score_start_week")),
            "endWeek": _int_or_none(row.get("score_end_week")),
        },
        "netPoints": net_points,
        "objectiveWinner": objective_winner,
        "scoreEligible": score_eligible,
        "scoreEligibility": {
            "eligible": score_eligible,
            "reason": None if score_eligible else ungraded_reason,
        },
        "gradeStatus": _text(row.get("grade_status")) or "unknown",
        "gradeMetadata": _grade_metadata(row),
        "ungradedReason": ungraded_reason,
        "caveats": _caveats(ungraded_reason, net_points, objective_winner),
        "sourceTransactionIds": _source_transaction_ids(row, source_trade_id),
        "sortKeys": {
            "bestTrade": net_points,
            "worstTrade": -net_points if net_points is not None else None,
        },
    }


def _sides(row: JsonObject, net_points: float | None) -> list[JsonValue]:
    winner_team_id = _int_or_none(row.get("winner_team_id"))
    opposite_net = -net_points if net_points is not None else None
    sides = [
        _side(row, "team_a", "teamA", net_points, winner_team_id),
        _side(row, "team_b", "teamB", opposite_net, winner_team_id),
    ]
    return [side for side in sides if _side_has_content(side)]


def _side(
    row: JsonObject,
    prefix: str,
    side_name: str,
    net_points: float | None,
    winner_team_id: int | None,
) -> JsonObject:
    team_id = _int_or_none(row.get(f"{prefix}_id"))
    return {
        "side": side_name,
        "teamId": team_id,
        "teamName": _text(row.get(f"{prefix}_name")),
        "managerKey": _manager_key(team_id),
        "receivedAssets": _assets(row.get(f"{prefix}_players")),
        "postTradePoints": _float_or_none(row.get(f"{prefix}_points")),
        "grade": _text(row.get(f"{prefix}_grade")),
        "netPoints": net_points,
        "isObjectiveWinner": team_id is not None and team_id == winner_team_id,
    }


def _assets(value: JsonValue) -> list[JsonValue]:
    if not isinstance(value, list):
        return []
    return [
        {
            "playerId": _int_or_none(item.get("playerId")),
            "name": _text(item.get("name")) or "Unknown Player",
            "fromTeamId": _int_or_none(item.get("fromTeamId")),
            "toTeamId": _int_or_none(item.get("toTeamId")),
            "postTradePoints": _float_or_none(item.get("post_trade_points")),
            "weeklyPoints": _json_object(item.get("weekly_points")),
        }
        for item in value
        if isinstance(item, dict)
    ]


def _winner_json(sides: list[JsonValue]) -> JsonObject | None:
    for side_value in sides:
        if not isinstance(side_value, dict):
            continue
        if side_value.get("isObjectiveWinner") is True:
            return {
                "side": _text(side_value.get("side")),
                "teamId": _int_or_none(side_value.get("teamId")),
                "teamName": _text(side_value.get("teamName")),
                "managerKey": _text(side_value.get("managerKey")),
            }
    return None


def _stable_trade_id(row: JsonObject, source_trade_id: str) -> str:
    canonical_key = _text(row.get("canonical_trade_key"))
    if canonical_key:
        return canonical_key
    season = _text(row.get("season")) or "unknown-season"
    return f"trade:{season}:{source_trade_id}"


def _source_transaction_ids(row: JsonObject, source_trade_id: str) -> list[JsonValue]:
    seen: set[str] = set()
    ordered: list[JsonValue] = []
    for candidate in (
        source_trade_id,
        _text(row.get("related_transaction_id")),
        _text(row.get("trade_item_source_transaction_id")),
    ):
        if candidate and candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


def _grade_metadata(row: JsonObject) -> JsonObject:
    return {
        "gradeStatus": _text(row.get("grade_status")) or "unknown",
        "teamAGrade": _text(row.get("team_a_grade")),
        "teamBGrade": _text(row.get("team_b_grade")),
        "canonicalTradeKey": _text(row.get("canonical_trade_key")),
        "canonicalGroupSize": _int_or_none(row.get("canonical_group_size")),
        "canonicalGroupTradeIds": _string_list(row.get("canonical_group_trade_ids")),
        "tradeItemSource": _text(row.get("trade_item_source")),
        "tradeItemSourceType": _text(row.get("trade_item_source_type")),
        "tradeItemSourceStatus": _text(row.get("trade_item_source_status")),
    }


def _caveats(
    ungraded_reason: str | None,
    net_points: float | None,
    objective_winner: JsonObject | None,
) -> list[JsonValue]:
    if ungraded_reason:
        return [f"Trade is visible but excluded from scoring: {ungraded_reason}"]
    if net_points is None or objective_winner is None:
        return ["Trade is visible but excluded from scoring: points or winner unresolved"]
    return []


def _manager_keys(sides: list[JsonValue]) -> list[JsonValue]:
    return [
        manager_key
        for side in sides
        if isinstance(side, dict)
        if (manager_key := _text(side.get("managerKey"))) is not None
    ]


def _team_ids(sides: list[JsonValue]) -> list[JsonValue]:
    return [
        team_id
        for side in sides
        if isinstance(side, dict)
        if (team_id := _int_or_none(side.get("teamId"))) is not None
    ]


def _side_field_float(sides: list[JsonValue], side_name: str, key: str) -> float | None:
    for side in sides:
        if isinstance(side, dict) and side.get("side") == side_name:
            return _float_or_none(side.get(key))
    return None


def _side_has_content(side: JsonObject) -> bool:
    return (
        side.get("teamId") is not None
        or side.get("teamName") is not None
        or bool(side.get("receivedAssets"))
    )


def _sort_key(row: JsonObject) -> tuple[int, int, str]:
    return (
        _int_or_none(row.get("season")) or 0,
        _int_or_none(row.get("week")) or 0,
        _text(row.get("tradeId")) or "",
    )


def _best_sort_key(row: JsonObject) -> tuple[bool, float, tuple[int, int, str]]:
    value = _sort_float(row, "bestTrade")
    return (value is None, -(value or 0.0), _sort_key(row))


def _sort_float(row: JsonObject, key: str) -> float | None:
    sort_keys = row.get("sortKeys")
    if not isinstance(sort_keys, dict):
        return None
    return _float_or_none(sort_keys.get(key))


def _matches_season(row: JsonObject, season: int | None) -> bool:
    return season is None or _int_or_none(row.get("season")) == season


def _matches_manager(row: JsonObject, manager_key: str | None, mine_only: bool) -> bool:
    if manager_key is None:
        return not mine_only
    manager_keys = row.get("managerKeys")
    return isinstance(manager_keys, list) and manager_key in manager_keys


def _fallback_source_trade_id(row: JsonObject) -> str:
    season = _text(row.get("season")) or "unknown-season"
    week = _text(row.get("week")) or "unknown-week"
    return f"{season}:{week}"


def _manager_key(team_id: int | None) -> str | None:
    return None if team_id is None else f"team:{team_id}"


def _json_object(value: JsonValue) -> JsonObject:
    return dict(value) if isinstance(value, dict) else {}


def _string_list(value: JsonValue) -> list[JsonValue]:
    if not isinstance(value, list):
        return []
    return [_text(item) or "" for item in value]


def _text(value: JsonValue) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, int | float):
        return str(value)
    return None


def _int_or_none(value: JsonValue) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _float_or_none(value: JsonValue) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
