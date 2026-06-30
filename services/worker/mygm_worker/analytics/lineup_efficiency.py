from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, final

from mygm_worker.analytics.identity import load_team_seasons
from mygm_worker.analytics.json_tools import (
    as_object,
    float_value,
    int_value,
    object_field,
    read_json,
)

if TYPE_CHECKING:
    from pathlib import Path

    from mygm_worker.analytics.models import JsonObject, JsonValue, ManagerIdentity, TeamSeason
    from mygm_worker.analytics.reader import FixtureReader

# ESPN lineup slot ids that are never part of a startable lineup.
NON_STARTING_SLOTS: Final[frozenset[int]] = frozenset({20, 21})  # 20 = bench, 21 = IR

# Static breadth of each starting slot (smaller = more positionally restrictive).
# A laminar (nested) eligibility structure means filling the most restrictive slots
# first with their highest scorers yields the optimal legal lineup.
_SLOT_BREADTH: Final[dict[int, int]] = {
    0: 1,  # QB
    2: 1,  # RB
    4: 1,  # WR
    6: 1,  # TE
    16: 1,  # D/ST
    17: 1,  # K
    3: 2,  # RB/WR
    5: 2,  # WR/TE
    23: 3,  # FLEX (RB/WR/TE)
    7: 4,  # OP / superflex (QB/RB/WR/TE)
}
_DEFAULT_BREADTH: Final = 5


@dataclass(frozen=True, slots=True)
class LineupEntry:
    points: float
    eligible_slots: frozenset[int]
    lineup_slot_id: int


@dataclass(frozen=True, slots=True)
class LineupSeasonRow:
    season: int
    team_id: int
    manager_key: str
    display_name: str
    team_name: str
    weeks_counted: int
    started_points: float
    optimal_points: float
    bench_points: float
    # Mean of the per-week (started / optimal) ratios, as a 0-100 percentage.
    avg_efficiency: float
    # Aggregate started / aggregate optimal, as a 0-100 percentage.
    aggregate_efficiency: float


def lineup_efficiency_rows(
    reader: FixtureReader,
    managers: dict[str, ManagerIdentity],
    team_seasons: list[TeamSeason],
) -> tuple[LineupSeasonRow, ...]:
    team_lookup = {(row.season, row.team_id): row for row in team_seasons}
    accumulators: dict[tuple[int, int], _Accumulator] = {}
    for season in reader.seasons():
        starting_slots = _starting_slots(reader, season.season)
        if not starting_slots:
            continue
        for team_id, started, optimal in _team_weeks(reader.root, season.season, starting_slots):
            key = (season.season, team_id)
            acc = accumulators.setdefault(key, _Accumulator())
            acc.add(started, optimal)
    rows = [
        _season_row(season, team_id, acc, team_lookup, managers)
        for (season, team_id), acc in sorted(accumulators.items())
    ]
    return tuple(row for row in rows if row is not None)


@final
class _Accumulator:
    __slots__ = ("optimal_total", "ratio_sum", "started_total", "weeks")

    def __init__(self) -> None:
        self.weeks: int = 0
        self.started_total: float = 0.0
        self.optimal_total: float = 0.0
        self.ratio_sum: float = 0.0

    def add(self, started: float, optimal: float) -> None:
        if optimal <= 0.0:
            return
        self.weeks += 1
        self.started_total += started
        self.optimal_total += optimal
        self.ratio_sum += min(started / optimal, 1.0)


def _season_row(
    season: int,
    team_id: int,
    acc: _Accumulator,
    team_lookup: dict[tuple[int, int], TeamSeason],
    managers: dict[str, ManagerIdentity],
) -> LineupSeasonRow | None:
    if acc.weeks == 0:
        return None
    team = team_lookup.get((season, team_id))
    manager_key = team.manager_key if team else f"unresolved:{season}:{team_id}"
    team_name = team.team_name if team else f"Team {team_id}"
    manager = managers.get(manager_key)
    display_name = manager.display_name if manager else manager_key
    avg = (acc.ratio_sum / acc.weeks) * 100
    aggregate = (acc.started_total / acc.optimal_total) * 100 if acc.optimal_total else 0.0
    return LineupSeasonRow(
        season=season,
        team_id=team_id,
        manager_key=manager_key,
        display_name=display_name,
        team_name=team_name,
        weeks_counted=acc.weeks,
        started_points=round(acc.started_total, 4),
        optimal_points=round(acc.optimal_total, 4),
        bench_points=round(acc.optimal_total - acc.started_total, 4),
        avg_efficiency=round(avg, 4),
        aggregate_efficiency=round(aggregate, 4),
    )


def _team_weeks(
    root: Path,
    season: int,
    starting_slots: dict[int, int],
) -> Iterator[tuple[int, float, float]]:
    season_dir = root / f"season_{season}"
    if not season_dir.is_dir():
        return
    for week_path in sorted((season_dir / "box_scores").glob("week_*.json")):
        payload = as_object(read_json(week_path), str(week_path))
        data = object_field(payload, "data")
        schedules = data.get("schedule")
        if not isinstance(schedules, list):
            continue
        for matchup in schedules:
            if not isinstance(matchup, dict):
                continue
            yield from _matchup_team_weeks(matchup, starting_slots)


def _matchup_team_weeks(
    matchup: JsonObject,
    starting_slots: dict[int, int],
) -> Iterator[tuple[int, float, float]]:
    for side_name in ("home", "away"):
        side = matchup.get(side_name)
        if not isinstance(side, dict):
            continue
        team_id = int_value(side.get("teamId"))
        if team_id == 0:
            continue
        entries = _entries(side)
        if not entries:
            continue
        started = sum(
            entry.points for entry in entries if entry.lineup_slot_id not in NON_STARTING_SLOTS
        )
        optimal = optimal_lineup_points(entries, starting_slots)
        if optimal <= 0.0:
            continue
        yield team_id, round(started, 4), round(optimal, 4)


def _entries(side: JsonObject) -> list[LineupEntry]:
    roster = side.get("rosterForCurrentScoringPeriod")
    if not isinstance(roster, dict):
        return []
    raw_entries = roster.get("entries")
    if not isinstance(raw_entries, list):
        return []
    entries: list[LineupEntry] = []
    for raw in raw_entries:
        if not isinstance(raw, dict):
            continue
        lineup_slot_id = int_value(raw.get("lineupSlotId"))
        pool_entry = raw.get("playerPoolEntry")
        if not isinstance(pool_entry, dict):
            continue
        points = float_value(pool_entry.get("appliedStatTotal"))
        player = pool_entry.get("player")
        eligible = _eligible_slots(player)
        entries.append(
            LineupEntry(points=points, eligible_slots=eligible, lineup_slot_id=lineup_slot_id)
        )
    return entries


def _eligible_slots(player: JsonValue) -> frozenset[int]:
    if not isinstance(player, dict):
        return frozenset()
    slots = player.get("eligibleSlots")
    if not isinstance(slots, list):
        return frozenset()
    return frozenset(int_value(slot) for slot in slots)


def optimal_lineup_points(entries: list[LineupEntry], starting_slots: dict[int, int]) -> float:
    # Build one instance per starting slot, ordered most-restrictive first.
    instances = sorted(
        (slot_id for slot_id, count in starting_slots.items() for _ in range(count)),
        key=lambda slot_id: (_SLOT_BREADTH.get(slot_id, _DEFAULT_BREADTH), slot_id),
    )
    # Only players who can fill at least one starting slot and are not on IR.
    pool = [entry for entry in entries if entry.lineup_slot_id != 21]
    used = [False] * len(pool)
    total = 0.0
    for slot_id in instances:
        best_index = -1
        best_points = 0.0
        for index, entry in enumerate(pool):
            if used[index] or slot_id not in entry.eligible_slots:
                continue
            if best_index == -1 or entry.points > best_points:
                best_index = index
                best_points = entry.points
        if best_index != -1:
            used[best_index] = True
            total += pool[best_index].points
    return total


def _starting_slots(reader: FixtureReader, season: int) -> dict[int, int]:
    core = reader.core(season)
    settings = core.get("settings")
    if not isinstance(settings, dict):
        return {}
    roster_settings = settings.get("rosterSettings")
    if not isinstance(roster_settings, dict):
        return {}
    slot_counts = roster_settings.get("lineupSlotCounts")
    if not isinstance(slot_counts, dict):
        return {}
    starting: dict[int, int] = {}
    for slot_text, count_value in slot_counts.items():
        slot_id = int_value(slot_text)
        count = int_value(count_value)
        if count > 0 and slot_id not in NON_STARTING_SLOTS:
            starting[slot_id] = count
    return starting


def lineup_efficiency_for_fixture(reader: FixtureReader) -> tuple[LineupSeasonRow, ...]:
    managers, team_seasons = load_team_seasons(reader)
    return lineup_efficiency_rows(reader, managers, team_seasons)
