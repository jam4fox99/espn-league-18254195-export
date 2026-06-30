from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from mygm_worker.analytics.json_tools import (
    as_object,
    float_value,
    int_value,
    object_field,
    read_json,
    string_value,
)

if TYPE_CHECKING:
    from pathlib import Path

    from mygm_worker.analytics.models import JsonObject, ManagerIdentity, TeamSeason
    from mygm_worker.analytics.reader import FixtureReader

# ESPN lineup slot ids that mean a player was not started.
NON_STARTING_SLOTS: Final[frozenset[int]] = frozenset({20, 21})  # 20 = bench, 21 = IR
# ESPN defaultPositionId -> fantasy position label.
_POSITIONS: Final[dict[int, str]] = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "D/ST"}
TOP_N: Final = 15
MIN_WEEKS_FOR_SEASON: Final = 4


@dataclass(frozen=True, slots=True)
class PlayerWeekRecord:
    player_id: int
    player_name: str
    position: str
    season: int
    week: int
    points: float
    manager_key: str
    display_name: str
    team_name: str


@dataclass(frozen=True, slots=True)
class PlayerSeasonRecord:
    player_id: int
    player_name: str
    position: str
    season: int
    points: float
    weeks: int
    manager_key: str
    display_name: str
    team_name: str


@dataclass(frozen=True, slots=True)
class PlayerLeaderboards:
    top_weeks: tuple[PlayerWeekRecord, ...]
    top_seasons: tuple[PlayerSeasonRecord, ...]


@dataclass(frozen=True, slots=True)
class _StartedWeek:
    player_id: int
    player_name: str
    position: str
    season: int
    week: int
    team_id: int
    points: float


def player_leaderboards(
    reader: FixtureReader,
    managers: dict[str, ManagerIdentity],
    team_seasons: list[TeamSeason],
) -> PlayerLeaderboards:
    team_lookup = {(row.season, row.team_id): row for row in team_seasons}
    started: list[_StartedWeek] = []
    for season in reader.seasons():
        started.extend(_season_started_weeks(reader.root, season.season))
    # Box scores always carry player ids; only build the (name -> id) backfill map (which
    # parses the large player lookup) when a started entry is actually missing its id.
    backfill = _name_id_backfill(reader) if any(week.player_id == 0 for week in started) else {}
    return PlayerLeaderboards(
        top_weeks=_top_weeks(started, team_lookup, managers, backfill),
        top_seasons=_top_seasons(started, team_lookup, managers, backfill),
    )


def _name_id_backfill(reader: FixtureReader) -> dict[str, int]:
    backfill: dict[str, int] = {}
    for player_id_text, player in reader.player_lookup().items():
        if not isinstance(player, dict):
            continue
        name = string_value(player.get("name"))
        if name and name not in backfill:
            backfill[name] = int_value(player_id_text)
    return backfill


def _resolve_player_id(player_id: int, name: str, backfill: dict[str, int]) -> int:
    if player_id != 0:
        return player_id
    return backfill.get(name, 0)


def _top_weeks(
    started: list[_StartedWeek],
    team_lookup: dict[tuple[int, int], TeamSeason],
    managers: dict[str, ManagerIdentity],
    backfill: dict[str, int],
) -> tuple[PlayerWeekRecord, ...]:
    ranked = sorted(started, key=lambda week: (-week.points, week.season, week.player_name))
    records: list[PlayerWeekRecord] = []
    for entry in ranked[:TOP_N]:
        manager_key, display_name, team_name = _attribution(
            entry.season, entry.team_id, team_lookup, managers,
        )
        records.append(
            PlayerWeekRecord(
                player_id=_resolve_player_id(entry.player_id, entry.player_name, backfill),
                player_name=entry.player_name,
                position=entry.position,
                season=entry.season,
                week=entry.week,
                points=entry.points,
                manager_key=manager_key,
                display_name=display_name,
                team_name=team_name,
            ),
        )
    return tuple(records)


def _top_seasons(
    started: list[_StartedWeek],
    team_lookup: dict[tuple[int, int], TeamSeason],
    managers: dict[str, ManagerIdentity],
    backfill: dict[str, int],
) -> tuple[PlayerSeasonRecord, ...]:
    totals: dict[tuple[int, int, int], list[float]] = defaultdict(list)
    names: dict[tuple[int, int, int], tuple[str, str]] = {}
    for entry in started:
        key = (entry.player_id, entry.season, entry.team_id)
        totals[key].append(entry.points)
        names[key] = (entry.player_name, entry.position)
    rows: list[PlayerSeasonRecord] = []
    for (player_id, season, team_id), points in totals.items():
        if len(points) < MIN_WEEKS_FOR_SEASON:
            continue
        name, position = names[(player_id, season, team_id)]
        manager_key, display_name, team_name = _attribution(season, team_id, team_lookup, managers)
        rows.append(
            PlayerSeasonRecord(
                player_id=_resolve_player_id(player_id, name, backfill),
                player_name=name,
                position=position,
                season=season,
                points=round(sum(points), 2),
                weeks=len(points),
                manager_key=manager_key,
                display_name=display_name,
                team_name=team_name,
            ),
        )
    rows.sort(key=lambda row: (-row.points, row.season, row.player_name))
    return tuple(rows[:TOP_N])


def _attribution(
    season: int,
    team_id: int,
    team_lookup: dict[tuple[int, int], TeamSeason],
    managers: dict[str, ManagerIdentity],
) -> tuple[str, str, str]:
    team = team_lookup.get((season, team_id))
    manager_key = team.manager_key if team else f"unresolved:{season}:{team_id}"
    team_name = team.team_name if team else f"Team {team_id}"
    manager = managers.get(manager_key)
    display_name = manager.display_name if manager else manager_key
    return manager_key, display_name, team_name


def _season_started_weeks(root: Path, season: int) -> Iterator[_StartedWeek]:
    season_dir = root / f"season_{season}"
    if not season_dir.is_dir():
        return
    for week_path in sorted((season_dir / "box_scores").glob("week_*.json")):
        week = _week_from_path(week_path)
        payload = as_object(read_json(week_path), str(week_path))
        data = object_field(payload, "data")
        schedules = data.get("schedule")
        if not isinstance(schedules, list):
            continue
        for matchup in schedules:
            if not isinstance(matchup, dict):
                continue
            for side_name in ("home", "away"):
                side = matchup.get(side_name)
                if not isinstance(side, dict):
                    continue
                team_id = int_value(side.get("teamId"))
                if team_id == 0:
                    continue
                yield from _side_started(side, season, week, team_id)


def _side_started(
    side: JsonObject,
    season: int,
    week: int,
    team_id: int,
) -> Iterator[_StartedWeek]:
    roster = side.get("rosterForCurrentScoringPeriod")
    if not isinstance(roster, dict):
        return
    entries = roster.get("entries")
    if not isinstance(entries, list):
        return
    for raw in entries:
        if not isinstance(raw, dict):
            continue
        if int_value(raw.get("lineupSlotId")) in NON_STARTING_SLOTS:
            continue
        pool = raw.get("playerPoolEntry")
        if not isinstance(pool, dict):
            continue
        player = pool.get("player")
        if not isinstance(player, dict):
            continue
        name = player.get("fullName")
        if not isinstance(name, str) or not name:
            continue
        yield _StartedWeek(
            player_id=int_value(player.get("id")),
            player_name=name,
            position=_POSITIONS.get(int_value(player.get("defaultPositionId")), "FLEX"),
            season=season,
            week=week,
            team_id=team_id,
            points=round(float_value(pool.get("appliedStatTotal")), 2),
        )


def _week_from_path(path: Path) -> int:
    stem = path.stem
    _, _, tail = stem.partition("_")
    return int_value(tail)
