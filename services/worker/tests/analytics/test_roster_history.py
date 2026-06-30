from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from mygm_worker.analytics.identity import load_team_seasons
from mygm_worker.analytics.json_tools import (
    as_array,
    as_object,
    float_value,
    int_value,
    string_value,
)
from mygm_worker.analytics.reader import FixtureReader
from mygm_worker.analytics.roster_history import roster_history

if TYPE_CHECKING:
    from mygm_worker.analytics.models import JsonObject

FIXTURE_ROOT = Path(__file__).parents[4] / "espn_exports" / "league_18254195"
_MIN_STARTED_GAMES = 3
_BASE_SLOTS = {"QB", "RB", "WR", "TE", "D/ST"}


def _history() -> dict[str, JsonObject]:
    reader = FixtureReader(FIXTURE_ROOT)
    managers, team_seasons = load_team_seasons(reader)
    return roster_history(reader, managers, team_seasons)


def _seasons_by_manager() -> dict[str, set[int]]:
    reader = FixtureReader(FIXTURE_ROOT)
    _, team_seasons = load_team_seasons(reader)
    seasons: dict[str, set[int]] = defaultdict(set)
    for row in team_seasons:
        seasons[row.manager_key].add(row.season)
    return seasons


def _full_tenure_manager() -> str:
    seasons = _seasons_by_manager()
    return max(sorted(seasons), key=lambda key: len(seasons[key]))


def test_all_time_lineup_fills_every_starting_slot_with_distinct_players() -> None:
    manager = _full_tenure_manager()
    lineup = as_array(_history()[manager]["allTimeLineup"], "allTimeLineup")

    assert lineup
    rows = [as_object(entry, "lineup entry") for entry in lineup]
    slots = [string_value(row["slot"]) for row in rows]
    player_ids = [int_value(row["playerId"]) for row in rows]

    # A full-tenure manager fills every dedicated base slot plus the flex.
    assert set(slots) >= _BASE_SLOTS
    assert "FLEX" in slots
    # The league starts two RBs and three WRs (read from lineupSlotCounts, max over seasons).
    assert slots.count("RB") == 2
    assert slots.count("WR") == 3
    # Distinct players across every slot.
    assert len(player_ids) == len(set(player_ids))
    # The three-started-games floor is enforced on every qualifying player-season.
    for row in rows:
        assert int_value(row["gamesStarted"]) >= _MIN_STARTED_GAMES
        assert string_value(row["name"])
        assert int_value(row["season"]) >= 2020


def test_depth_chart_has_at_least_one_entry_per_filled_position() -> None:
    manager = _full_tenure_manager()
    chart = as_object(_history()[manager]["depthChart"], "depthChart")

    assert chart
    for position, entries in chart.items():
        rows = [as_object(entry, "depth entry") for entry in as_array(entries, position)]
        assert rows
        assert len(rows) <= _MIN_STARTED_GAMES
        # Each rank is a distinct player-season ordered by points per game (descending).
        ppgs = [float_value(row["ppg"]) for row in rows]
        assert ppgs == sorted(ppgs, reverse=True)
        for row in rows:
            assert string_value(row["position"]) == position
            assert int_value(row["gamesStarted"]) >= _MIN_STARTED_GAMES


def test_season_rosters_cover_every_played_season() -> None:
    reader = FixtureReader(FIXTURE_ROOT)
    partial_seasons = {season.season for season in reader.seasons() if season.is_partial}
    manager = _full_tenure_manager()
    manager_seasons = _seasons_by_manager()[manager]

    season_rosters = as_array(_history()[manager]["seasonRosters"], "seasonRosters")
    covered = {int_value(as_object(row, "season roster")["season"]) for row in season_rosters}

    # Every completed season the manager played shows up; partial seasons (no final week) drop.
    assert covered <= manager_seasons
    assert (manager_seasons - partial_seasons) <= covered
    for row in season_rosters:
        groups = as_array(as_object(row, "season roster")["groups"], "groups")
        assert groups
        for group in groups:
            players = as_array(as_object(group, "group")["players"], "players")
            assert players


def test_cornerstones_rank_by_weeks_started() -> None:
    manager = _full_tenure_manager()
    cornerstones = as_array(_history()[manager]["cornerstones"], "cornerstones")

    assert cornerstones
    weeks = [int_value(as_object(row, "cornerstone")["weeksStarted"]) for row in cornerstones]
    assert weeks[0] > 0
    assert weeks == sorted(weeks, reverse=True)


def test_best_season_snapshot_matches_a_played_lineup() -> None:
    manager = _full_tenure_manager()
    best = as_object(_history()[manager]["bestSeason"], "bestSeason")

    assert string_value(best["metric"]) == "pointsFor"
    lineup = as_array(best["lineup"], "bestSeason.lineup")
    assert lineup
    # The snapshot is a real starting lineup, not the whole season of starters used.
    slots = [string_value(as_object(entry, "entry")["slot"]) for entry in lineup]
    assert "QB" in slots
    assert len(lineup) <= 11
