from __future__ import annotations

# pyright: reportAny=false, reportArgumentType=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportExplicitAny=false, reportImplicitStringConcatenation=false, reportImportCycles=false, reportOperatorIssue=false, reportUnannotatedClassAttribute=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false, reportUnusedCallResult=false
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

POSITION_MAP = {
    0: "QB",
    2: "RB",
    4: "WR",
    6: "TE",
    16: "D/ST",
    17: "K",
}

LINEUP_SLOT_MAP = {
    0: "QB",
    2: "RB",
    4: "WR",
    6: "TE",
    16: "D/ST",
    17: "K",
    20: "BE",
    21: "IR",
    23: "FLEX",
}

STARTING_LINEUP_SLOTS = {0, 2, 4, 6, 16, 17, 23}


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def season_from_dir(path: Path) -> int:
    return int(path.name.split("_", 1)[1])


def week_from_file(path: Path) -> int:
    return int(path.stem.split("_", 1)[1])


def player_name(player: dict[str, Any]) -> str | None:
    full = player.get("fullName")
    if full:
        return str(full)
    first = player.get("firstName")
    last = player.get("lastName")
    if first or last:
        return " ".join(part for part in [first, last] if part)
    return None


def clean_points(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def pick_stat(
    stats: list[dict[str, Any]],
    season: int,
    week: int,
    stat_source_id: int,
) -> dict[str, Any] | None:
    for stat in stats:
        if (
            stat.get("seasonId") == season
            and stat.get("scoringPeriodId") == week
            and stat.get("statSourceId") == stat_source_id
            and stat.get("statSplitTypeId") == 1
        ):
            return stat
    return None


def empty_player(player_id: int) -> dict[str, Any]:
    return {
        "playerId": player_id,
        "name": None,
        "firstName": None,
        "lastName": None,
        "defaultPositionId": None,
        "defaultPosition": None,
        "proTeamIds": [],
        "name_sources": [],
        "weekly_points": {},
        "weekly_details": {},
        "box_score_appearances": [],
        "trade_contexts": [],
        "sources": [],
    }


def append_unique(values: list[Any], value: Any) -> None:
    if value is not None and value not in values:
        values.append(value)


def merge_player_meta(
    players: dict[str, dict[str, Any]],
    player_id: int,
    player: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    record = players.setdefault(str(player_id), empty_player(player_id))
    name = player_name(player)
    if name and not record["name"]:
        record["name"] = name
    if player.get("firstName") and not record["firstName"]:
        record["firstName"] = player.get("firstName")
    if player.get("lastName") and not record["lastName"]:
        record["lastName"] = player.get("lastName")
    if player.get("defaultPositionId") is not None:
        record["defaultPositionId"] = player.get("defaultPositionId")
        record["defaultPosition"] = POSITION_MAP.get(player.get("defaultPositionId"))
    append_unique(record["proTeamIds"], player.get("proTeamId"))
    append_unique(record["name_sources"], source if name else None)
    append_unique(record["sources"], source)
    return record


def set_weekly_point(
    player_record: dict[str, Any],
    season: int,
    week: int,
    points: float | None,
    source: str,
    detail_updates: dict[str, Any] | None = None,
) -> None:
    if points is None:
        return

    season_key = str(season)
    week_key = str(week)
    player_record["weekly_points"].setdefault(season_key, {})
    player_record["weekly_details"].setdefault(season_key, {})
    detail = player_record["weekly_details"][season_key].setdefault(
        week_key,
        {"points": points, "source": source, "sources": []},
    )

    old_points = detail.get("points")
    if old_points is None or source == "player_card_actual":
        detail["points"] = points
        detail["source"] = source
    elif old_points != points:
        conflicts = detail.setdefault("point_conflicts", [])
        conflict = {"source": source, "points": points}
        if conflict not in conflicts:
            conflicts.append(conflict)

    append_unique(detail["sources"], source)
    if detail_updates:
        for key, value in detail_updates.items():
            if key == "appearances":
                detail.setdefault("appearances", [])
                detail["appearances"].extend(value)
            elif value is not None:
                detail[key] = value

    player_record["weekly_points"][season_key][week_key] = detail["points"]
