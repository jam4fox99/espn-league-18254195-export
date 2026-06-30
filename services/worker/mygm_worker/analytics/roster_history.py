"""Per-manager roster-history views derived from box-score appearances.

Every view is built from each player's ``box_score_appearances`` (which carry the
``isStarter`` flag and the ``lineupSlotId`` a player was started in each week) joined to
``weekly_points``. The starting-lineup shape is read from each season's
``settings.rosterSettings.lineupSlotCounts`` so the engine is league-agnostic: it never
hardcodes how many QB/RB/WR/TE/FLEX/K/DST a league starts.

A *player-season* is the unit of every "all-time" view. Its rate stat is points per game
**over the weeks the manager started that player** (a started game floors at
``_MIN_STARTED_GAMES``); ``totalPoints`` is the sum over those same started weeks — the
points the player actually delivered from this manager's lineup.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from mygm_worker.analytics.json_tools import as_object, float_value, int_value
from mygm_worker.analytics.player_directory import build_player_directory

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from mygm_worker.analytics.models import JsonObject, JsonValue, ManagerIdentity, TeamSeason
    from mygm_worker.analytics.player_directory import PlayerDirectoryEntry
    from mygm_worker.analytics.reader import FixtureReader

# Lineup slot ids that are never part of the starting lineup (bench, IR, taxi/empty).
_BENCH_SLOTS: Final = frozenset({20, 21, 24})
# Each dedicated lineup slot id -> the single fantasy position it starts.
_DEDICATED_SLOT_POSITION: Final[dict[int, str]] = {
    0: "QB",
    1: "QB",
    2: "RB",
    4: "WR",
    6: "TE",
    16: "D/ST",
    17: "K",
}
# Flex-type lineup slot ids -> the positions eligible to fill them.
_FLEX_SLOT_POSITIONS: Final[dict[int, frozenset[str]]] = {
    3: frozenset({"RB", "WR"}),
    5: frozenset({"WR", "TE"}),
    7: frozenset({"QB", "RB", "WR", "TE"}),
    23: frozenset({"RB", "WR", "TE"}),
}
# Display label per lineup slot id.
_SLOT_LABEL: Final[dict[int, str]] = {
    0: "QB",
    1: "QB",
    2: "RB",
    3: "RB/WR",
    4: "WR",
    5: "WR/TE",
    6: "TE",
    7: "SUPERFLEX",
    16: "D/ST",
    17: "K",
    23: "FLEX",
}
# Order starting slots read cleanly as a lineup card (offense, flex, then K/DST).
_SLOT_ORDER: Final[tuple[int, ...]] = (0, 1, 2, 3, 4, 5, 6, 23, 7, 17, 16)
_POSITION_ORDER: Final[tuple[str, ...]] = ("QB", "RB", "WR", "TE", "K", "D/ST")

_MIN_STARTED_GAMES: Final = 3
_DEPTH: Final = 3
_CORNERSTONE_LIMIT: Final = 12


def roster_history(
    reader: FixtureReader,
    managers: dict[str, ManagerIdentity],
    team_seasons: list[TeamSeason],
    *,
    directory: dict[int, PlayerDirectoryEntry] | None = None,
) -> dict[str, JsonObject]:
    resolved = directory if directory is not None else build_player_directory(reader)
    team_lookup = {(row.season, row.team_id): row.manager_key for row in team_seasons}
    final_weeks = {season.season: season.final_week for season in reader.seasons()}
    season_slots = _season_slot_counts(reader)
    manager_seasons = _manager_seasons(team_seasons)
    points_for = _points_for(team_seasons)
    index = _build_index(reader, resolved, team_lookup, final_weeks)
    candidates = _candidates(index.player_seasons, resolved)
    return {
        manager_key: _manager_history(
            manager_key,
            template=_manager_template(manager_seasons.get(manager_key, set()), season_slots),
            candidates=candidates.get(manager_key, ()),
            index=index,
            points_for=points_for.get(manager_key, {}),
            seasons=sorted(manager_seasons.get(manager_key, set())),
            season_slots=season_slots,
        )
        for manager_key in sorted(managers)
        if manager_key in index.managers
    }


@dataclass(slots=True)
class _Acc:
    games: int = 0
    points: float = 0.0


@dataclass(slots=True)
class _CornerAcc:
    weeks_started: int = 0
    points: float = 0.0
    seasons: set[int] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class _FinalEntry:
    player_id: int
    slot_id: int
    is_starter: bool


@dataclass(slots=True)
class _Index:
    managers: set[str]
    # (manager_key, season, slot_id, player_id) -> started games + points at that slot.
    slot_starts: dict[tuple[str, int, int, int], _Acc]
    # (manager_key, player_id, season) -> started games + points across all starting slots.
    player_seasons: dict[tuple[str, int, int], _Acc]
    # (manager_key, player_id) -> career started weeks for the cornerstone ranking.
    cornerstones: dict[tuple[str, int], _CornerAcc]
    # (manager_key, season) -> the manager's final-week roster (starters + bench).
    final_rosters: dict[tuple[str, int], list[_FinalEntry]]
    # (player_id, season) -> the player's full-season points (every scored week).
    season_total: dict[tuple[int, int], float]
    directory: dict[int, PlayerDirectoryEntry]

    def name(self, player_id: int) -> tuple[str, str, str]:
        entry = self.directory.get(player_id)
        if entry is None:
            return (f"Player {player_id}", "", "")
        return (entry.name, entry.position, entry.pro_team_abbrev)


@dataclass(frozen=True, slots=True)
class _Candidate:
    player_id: int
    name: str
    position: str
    pro_team: str
    season: int
    games: int
    total_points: float

    @property
    def ppg(self) -> float:
        return self.total_points / self.games if self.games else 0.0


def _by_ppg(cand: _Candidate) -> tuple[float, float]:
    return (cand.ppg, cand.total_points)


def _by_total_points(cand: _Candidate) -> tuple[float, float]:
    return (cand.total_points, cand.ppg)


def _build_index(
    reader: FixtureReader,
    directory: dict[int, PlayerDirectoryEntry],
    team_lookup: dict[tuple[int, int], str],
    final_weeks: dict[int, int],
) -> _Index:
    index = _Index(
        managers=set(),
        slot_starts=defaultdict(_Acc),
        player_seasons=defaultdict(_Acc),
        cornerstones=defaultdict(_CornerAcc),
        final_rosters=defaultdict(list),
        season_total={},
        directory=directory,
    )
    for player_id_text, player in reader.player_lookup().items():
        if not isinstance(player, dict):
            continue
        player_id = int_value(player.get("playerId")) or int_value(player_id_text)
        weekly = player.get("weekly_points")
        _absorb_season_totals(index, player_id, weekly)
        appearances = player.get("box_score_appearances")
        if not isinstance(appearances, list):
            continue
        for appearance in appearances:
            if isinstance(appearance, dict):
                _absorb_appearance(index, player_id, appearance, weekly, team_lookup, final_weeks)
    return index


def _absorb_season_totals(index: _Index, player_id: int, weekly: JsonValue) -> None:
    if not isinstance(weekly, dict):
        return
    for season_text, weeks in weekly.items():
        if isinstance(weeks, dict):
            total = sum(float_value(value) for value in weeks.values())
            index.season_total[(player_id, int_value(season_text))] = round(total, 4)


def _absorb_appearance(
    index: _Index,
    player_id: int,
    appearance: JsonObject,
    weekly: JsonValue,
    team_lookup: dict[tuple[int, int], str],
    final_weeks: dict[int, int],
) -> None:
    season = int_value(appearance.get("season"))
    manager_key = team_lookup.get((season, int_value(appearance.get("teamId"))))
    if manager_key is None:
        return
    index.managers.add(manager_key)
    week = int_value(appearance.get("week"))
    slot_id = int_value(appearance.get("lineupSlotId"))
    if week == final_weeks.get(season):
        index.final_rosters[(manager_key, season)].append(
            _FinalEntry(player_id, slot_id, appearance.get("isStarter") is True)
        )
    if appearance.get("isStarter") is not True or slot_id in _BENCH_SLOTS:
        return
    points = _week_points(weekly, season, week)
    slot_acc = index.slot_starts[(manager_key, season, slot_id, player_id)]
    slot_acc.games += 1
    slot_acc.points += points
    season_acc = index.player_seasons[(manager_key, player_id, season)]
    season_acc.games += 1
    season_acc.points += points
    corner = index.cornerstones[(manager_key, player_id)]
    corner.weeks_started += 1
    corner.points += points
    corner.seasons.add(season)


def _week_points(weekly: JsonValue, season: int, week: int) -> float:
    if not isinstance(weekly, dict):
        return 0.0
    season_weeks = weekly.get(str(season))
    if not isinstance(season_weeks, dict):
        return 0.0
    return float_value(season_weeks.get(str(week)))


def _candidates(
    player_seasons: dict[tuple[str, int, int], _Acc],
    directory: dict[int, PlayerDirectoryEntry],
) -> dict[str, list[_Candidate]]:
    by_manager: dict[str, list[_Candidate]] = defaultdict(list)
    for (manager_key, player_id, season), acc in player_seasons.items():
        if acc.games < _MIN_STARTED_GAMES:
            continue
        entry = directory.get(player_id)
        position = entry.position if entry is not None else ""
        if not position:
            continue
        by_manager[manager_key].append(
            _Candidate(
                player_id=player_id,
                name=entry.name if entry is not None else f"Player {player_id}",
                position=position,
                pro_team=entry.pro_team_abbrev if entry is not None else "",
                season=season,
                games=acc.games,
                total_points=round(acc.points, 4),
            )
        )
    return by_manager


def _manager_history(
    manager_key: str,
    *,
    template: list[tuple[int, int]],
    candidates: Iterable[_Candidate],
    index: _Index,
    points_for: dict[int, float],
    seasons: list[int],
    season_slots: dict[int, list[tuple[int, int]]],
) -> JsonObject:
    pool = list(candidates)
    return {
        "allTimeLineup": _lineup(template, pool, by_total=False),
        "allTimeByTotalPoints": _lineup(template, pool, by_total=True),
        "depthChart": _depth_chart(pool),
        "cornerstones": _cornerstones(manager_key, index),
        "bestSeason": _best_season(manager_key, points_for, index, season_slots),
        "seasonRosters": _season_rosters(manager_key, index, seasons),
    }


def _lineup(
    template: list[tuple[int, int]],
    candidates: list[_Candidate],
    *,
    by_total: bool,
) -> list[JsonValue]:
    ranked = sorted(candidates, key=_by_total_points if by_total else _by_ppg, reverse=True)
    used: set[int] = set()
    filled: list[tuple[int, _Candidate]] = []
    for slot_id, count in template:
        position = _DEDICATED_SLOT_POSITION.get(slot_id)
        if position is not None:
            _claim(ranked, used, filled, slot_id, count, lambda c, p=position: c.position == p)
    for slot_id, count in template:
        eligible = _FLEX_SLOT_POSITIONS.get(slot_id)
        if eligible is not None:
            _claim(ranked, used, filled, slot_id, count, lambda c, e=eligible: c.position in e)
    order = {slot_id: rank for rank, slot_id in enumerate(_SLOT_ORDER)}
    filled.sort(key=lambda item: order.get(item[0], len(order)))
    return [_entry(cand, _SLOT_LABEL.get(slot_id, cand.position)) for slot_id, cand in filled]


def _claim(
    ranked: list[_Candidate],
    used: set[int],
    filled: list[tuple[int, _Candidate]],
    slot_id: int,
    count: int,
    predicate: Callable[[_Candidate], bool],
) -> None:
    taken = 0
    for cand in ranked:
        if taken >= count:
            break
        if cand.player_id in used or not predicate(cand):
            continue
        filled.append((slot_id, cand))
        used.add(cand.player_id)
        taken += 1


def _depth_chart(candidates: list[_Candidate]) -> JsonObject:
    by_position: dict[str, list[_Candidate]] = defaultdict(list)
    for cand in candidates:
        by_position[cand.position].append(cand)
    chart: JsonObject = {}
    for position in _POSITION_ORDER:
        pool = by_position.get(position)
        if not pool:
            continue
        ranked = sorted(pool, key=lambda c: (c.ppg, c.total_points), reverse=True)
        seen: set[int] = set()
        rows: list[JsonValue] = []
        for cand in ranked:
            if cand.player_id in seen:
                continue
            seen.add(cand.player_id)
            rows.append(_entry(cand, position))
            if len(rows) >= _DEPTH:
                break
        chart[position] = rows
    return chart


def _cornerstones(manager_key: str, index: _Index) -> list[JsonValue]:
    rows: list[tuple[int, float, JsonObject]] = []
    for (key, player_id), acc in index.cornerstones.items():
        if key != manager_key:
            continue
        name, position, pro_team = index.name(player_id)
        rows.append(
            (
                acc.weeks_started,
                round(acc.points, 4),
                {
                    "playerId": player_id,
                    "name": name,
                    "position": position,
                    "proTeam": pro_team,
                    "weeksStarted": acc.weeks_started,
                    "totalPoints": round(acc.points, 4),
                    "firstSeason": min(acc.seasons) if acc.seasons else 0,
                    "lastSeason": max(acc.seasons) if acc.seasons else 0,
                    "seasonCount": len(acc.seasons),
                },
            )
        )
    rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [row for _, _, row in rows[:_CORNERSTONE_LIMIT]]


def _best_season(
    manager_key: str,
    points_for: dict[int, float],
    index: _Index,
    season_slots: dict[int, list[tuple[int, int]]],
) -> JsonValue:
    if not points_for:
        return None
    season, value = max(points_for.items(), key=lambda item: item[1])
    return {
        "season": season,
        "metric": "pointsFor",
        "pointsFor": round(value, 4),
        "lineup": _season_snapshot(manager_key, season, index, season_slots.get(season, [])),
    }


def _season_snapshot(
    manager_key: str,
    season: int,
    index: _Index,
    template: list[tuple[int, int]],
) -> list[JsonValue]:
    by_slot: dict[int, list[tuple[int, _Acc]]] = defaultdict(list)
    for (key, slot_season, slot_id, player_id), acc in index.slot_starts.items():
        if key == manager_key and slot_season == season:
            by_slot[slot_id].append((player_id, acc))
    snapshot: list[JsonValue] = []
    for slot_id, count in template:
        ranked = sorted(by_slot.get(slot_id, ()), key=_slot_play_rank, reverse=True)
        for player_id, acc in ranked[:count]:
            name, position, pro_team = index.name(player_id)
            snapshot.append(
                {
                    "playerId": player_id,
                    "name": name,
                    "position": position,
                    "slot": _SLOT_LABEL.get(slot_id, position),
                    "gamesStarted": acc.games,
                    "ppg": round(acc.points / acc.games, 4) if acc.games else 0.0,
                    "totalPoints": round(index.season_total.get((player_id, season), 0.0), 4),
                    "proTeam": pro_team,
                }
            )
    return snapshot


def _slot_play_rank(pair: tuple[int, _Acc]) -> tuple[int, float]:
    return (pair[1].games, pair[1].points)


def _season_rosters(manager_key: str, index: _Index, seasons: list[int]) -> list[JsonValue]:
    out: list[JsonValue] = []
    for season in seasons:
        entries = index.final_rosters.get((manager_key, season))
        if not entries:
            continue
        by_position: dict[str, list[JsonValue]] = defaultdict(list)
        for final in entries:
            name, position, pro_team = index.name(final.player_id)
            bucket = position or _SLOT_LABEL.get(final.slot_id, "FLEX")
            is_bench = final.slot_id in _BENCH_SLOTS
            by_position[bucket].append(
                {
                    "playerId": final.player_id,
                    "name": name,
                    "position": position,
                    "slot": _SLOT_LABEL.get(final.slot_id, "BE" if is_bench else ""),
                    "started": final.is_starter and not is_bench,
                    "totalPoints": round(index.season_total.get((final.player_id, season), 0.0), 4),
                    "proTeam": pro_team,
                }
            )
        out.append({"season": season, "groups": _roster_groups(by_position)})
    return out


def _roster_row_points(row: JsonValue) -> float:
    return float_value(as_object(row, "row").get("totalPoints"))


def _roster_groups(by_position: dict[str, list[JsonValue]]) -> list[JsonValue]:
    ordered = [*_POSITION_ORDER, *sorted(set(by_position) - set(_POSITION_ORDER))]
    groups: list[JsonValue] = []
    for position in ordered:
        rows = by_position.get(position)
        if not rows:
            continue
        rows.sort(key=_roster_row_points, reverse=True)
        groups.append({"position": position, "players": rows})
    return groups


def _entry(cand: _Candidate, slot: str) -> JsonObject:
    return {
        "playerId": cand.player_id,
        "name": cand.name,
        "position": cand.position,
        "slot": slot,
        "season": cand.season,
        "ppg": round(cand.ppg, 4),
        "gamesStarted": cand.games,
        "totalPoints": round(cand.total_points, 4),
        "proTeam": cand.pro_team,
    }


def _season_slot_counts(reader: FixtureReader) -> dict[int, list[tuple[int, int]]]:
    counts: dict[int, list[tuple[int, int]]] = {}
    for season in reader.seasons():
        slot_counts = _lineup_slot_counts(reader.core(season.season))
        counts[season.season] = [
            (slot_id, slot_counts[slot_id])
            for slot_id in _SLOT_ORDER
            if slot_counts.get(slot_id, 0) > 0
        ]
    return counts


def _lineup_slot_counts(core: JsonObject) -> dict[int, int]:
    settings = core.get("settings")
    settings_obj = settings if isinstance(settings, dict) else {}
    roster = settings_obj.get("rosterSettings")
    raw = roster.get("lineupSlotCounts") if isinstance(roster, dict) else None
    if not isinstance(raw, dict):
        raw = settings_obj.get("lineupSlotCounts")
    counts: dict[int, int] = {}
    if isinstance(raw, dict):
        for slot_text, count in raw.items():
            counts[int_value(slot_text)] = int_value(count)
    return counts


def _manager_template(
    seasons: set[int],
    season_slots: dict[int, list[tuple[int, int]]],
) -> list[tuple[int, int]]:
    max_count: dict[int, int] = {}
    for season in seasons:
        for slot_id, count in season_slots.get(season, ()):
            max_count[slot_id] = max(max_count.get(slot_id, 0), count)
    return [(slot_id, max_count[slot_id]) for slot_id in _SLOT_ORDER if slot_id in max_count]


def _manager_seasons(team_seasons: list[TeamSeason]) -> dict[str, set[int]]:
    seasons: dict[str, set[int]] = defaultdict(set)
    for row in team_seasons:
        seasons[row.manager_key].add(row.season)
    return seasons


def _points_for(team_seasons: list[TeamSeason]) -> dict[str, dict[int, float]]:
    points: dict[str, dict[int, float]] = defaultdict(dict)
    for row in team_seasons:
        points[row.manager_key][row.season] = row.points_for
    return points
