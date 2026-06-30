"""Roster-fit (positional need) engine for trade grading.

At a trade's scoring period, each team's *season-to-date points-by-position from
started players* is ranked against the league that season. A team in the bottom of
the league at a position has a **need** there; acquiring value at a need position is a
good fit. Need runs on QB/RB/WR/TE only (K/D-ST are excluded from fit).

Early in a season there is too little started-player data to read need, so the engine
falls back to the manager's **prior-season** full-season positional finish. With no
prior-season signal either, need is neutral (0.5) so fit neither helps nor hurts.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from mygm_worker.analytics.json_tools import (
    as_object,
    float_value,
    int_value,
    object_field,
    read_json,
)
from mygm_worker.analytics.player_directory import POSITIONS

if TYPE_CHECKING:
    from pathlib import Path

    from mygm_worker.analytics.models import JsonObject, JsonValue, TeamSeason
    from mygm_worker.analytics.reader import FixtureReader

# Need is meaningful only for the skill positions a manager actively shops for.
FIT_POSITIONS: Final = frozenset({"QB", "RB", "WR", "TE"})

# Lineup slot ids that are not part of a started lineup (bench / IR).
_NON_STARTING_SLOTS: Final = frozenset({20, 21})

# Minimum distinct weeks of started data before season-to-date need is trusted; below
# this the engine falls back to the prior season.
_EARLY_SEASON_WEEKS: Final = 3
_NEUTRAL_NEED: Final = 0.5


@dataclass(frozen=True, slots=True)
class FitIndex:
    # (season, manager_key) -> position -> list of (week, started_points), week-sorted.
    _by_manager: dict[tuple[int, str], dict[str, list[tuple[int, float]]]]
    _seasons: tuple[int, ...]

    def need(self, season: int, manager_key: str, as_of_week: int, position: str) -> float:
        """Need at ``position`` for ``manager_key`` as of ``as_of_week`` (0..1, 1 = strong need).

        Bottom-of-league at a position reads as high need; at/above the league median,
        need is 0. No signal (early season, no prior year) reads as no need.
        """
        percentile = self._positional_percentile(season, manager_key, as_of_week, position)
        if percentile is None:
            return 0.0
        return _need_from_percentile(percentile)

    def fit_value(self, season: int, manager_key: str, as_of_week: int, position: str) -> float:
        """Centered fit at ``position`` (0..1): 1 = filled a league-worst hole, 0.5 = neutral,
        0 = piled onto a league-best strength. No signal reads as neutral (0.5)."""
        percentile = self._positional_percentile(season, manager_key, as_of_week, position)
        if percentile is None:
            return _NEUTRAL_NEED
        return round(1.0 - percentile, 4)

    def _positional_percentile(
        self, season: int, manager_key: str, as_of_week: int, position: str
    ) -> float | None:
        if position not in FIT_POSITIONS:
            return None
        weeks_seen = self._weeks_seen(season, manager_key, as_of_week)
        if weeks_seen >= _EARLY_SEASON_WEEKS:
            values = self._cumulative_by_manager(season, as_of_week, position)
        elif season - 1 in self._seasons:
            values = self._cumulative_by_manager(season - 1, _FULL_SEASON, position)
        else:
            return None
        own = values.get(manager_key)
        if own is None or len(values) < 2:
            return None
        return _percentile(own, list(values.values()))

    def _weeks_seen(self, season: int, manager_key: str, as_of_week: int) -> int:
        positions = self._by_manager.get((season, manager_key))
        if not positions:
            return 0
        weeks: set[int] = set()
        for entries in positions.values():
            weeks.update(week for week, _ in entries if week <= as_of_week)
        return len(weeks)

    def _cumulative_by_manager(
        self, season: int, as_of_week: int, position: str
    ) -> dict[str, float]:
        totals: dict[str, float] = {}
        for (row_season, manager_key), positions in self._by_manager.items():
            if row_season != season:
                continue
            entries = positions.get(position, [])
            totals[manager_key] = round(
                sum(points for week, points in entries if week <= as_of_week), 4
            )
        return totals


_FULL_SEASON: Final = 10_000  # an as-of week past any real week => full-season totals.


def build_fit_index(reader: FixtureReader, team_seasons: list[TeamSeason]) -> FitIndex:
    team_lookup = {(row.season, row.team_id): row.manager_key for row in team_seasons}
    by_manager: defaultdict[tuple[int, str], dict[str, list[tuple[int, float]]]] = defaultdict(dict)
    seasons: set[int] = set()
    for season_meta in reader.seasons():
        season = season_meta.season
        seasons.add(season)
        for team_id, week, position, points in _started_rows(reader.root, season):
            manager_key = team_lookup.get((season, team_id))
            if manager_key is None or position not in FIT_POSITIONS:
                continue
            positions = by_manager[(season, manager_key)]
            positions.setdefault(position, []).append((week, points))
    return FitIndex(
        _by_manager={key: _sorted_positions(value) for key, value in by_manager.items()},
        _seasons=tuple(sorted(seasons)),
    )


def _sorted_positions(
    positions: dict[str, list[tuple[int, float]]],
) -> dict[str, list[tuple[int, float]]]:
    return {position: sorted(entries) for position, entries in positions.items()}


def _started_rows(root: Path, season: int) -> list[tuple[int, int, str, float]]:
    season_dir = root / f"season_{season}"
    if not season_dir.is_dir():
        return []
    rows: list[tuple[int, int, str, float]] = []
    for week_path in sorted((season_dir / "box_scores").glob("week_*.json")):
        week = _week_from_path(week_path.stem)
        payload = as_object(read_json(week_path), str(week_path))
        data = object_field(payload, "data")
        schedule = data.get("schedule")
        if not isinstance(schedule, list):
            continue
        for matchup in schedule:
            if isinstance(matchup, dict):
                rows.extend(_matchup_started_rows(matchup, week))
    return rows


def _matchup_started_rows(matchup: JsonObject, week: int) -> list[tuple[int, int, str, float]]:
    rows: list[tuple[int, int, str, float]] = []
    for side_name in ("home", "away"):
        side = matchup.get(side_name)
        if not isinstance(side, dict):
            continue
        team_id = int_value(side.get("teamId"))
        if team_id == 0:
            continue
        roster = side.get("rosterForCurrentScoringPeriod")
        if not isinstance(roster, dict):
            continue
        entries = roster.get("entries")
        if not isinstance(entries, list):
            continue
        for raw in entries:
            row = _started_entry(raw, team_id, week)
            if row is not None:
                rows.append(row)
    return rows


def _started_entry(
    raw: JsonValue, team_id: int, week: int
) -> tuple[int, int, str, float] | None:
    if not isinstance(raw, dict):
        return None
    if int_value(raw.get("lineupSlotId")) in _NON_STARTING_SLOTS:
        return None
    pool = raw.get("playerPoolEntry")
    if not isinstance(pool, dict):
        return None
    player = pool.get("player")
    if not isinstance(player, dict):
        return None
    position = POSITIONS.get(int_value(player.get("defaultPositionId")), "")
    if position not in FIT_POSITIONS:
        return None
    return team_id, week, position, float_value(pool.get("appliedStatTotal"))


def _percentile(value: float, values: list[float]) -> float:
    if len(values) < 2:
        return _NEUTRAL_NEED
    lower_or_equal = sum(1 for other in values if other <= value)
    return (lower_or_equal - 1) / (len(values) - 1)


def _need_from_percentile(percentile: float) -> float:
    # Below-median teams carry need that rises to 1 at the league floor; at/above the
    # median, need is 0. Continuous version of "bottom third = need".
    return round(max(0.0, (_NEUTRAL_NEED - percentile) * 2), 4)


def _week_from_path(stem: str) -> int:
    _, _, tail = stem.partition("_")
    return int_value(tail)
