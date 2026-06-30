from __future__ import annotations

from pathlib import Path

from mygm_worker.analytics.head_to_head import head_to_head_pairs
from mygm_worker.analytics.identity import load_team_seasons
from mygm_worker.analytics.reader import FixtureReader
from mygm_worker.analytics.records import (
    luck_strength_rows,
    record_rows,
)

FIXTURE_ROOT = Path(__file__).parents[4] / "espn_exports" / "league_18254195"


def test_records_include_supported_league_categories() -> None:
    # Given: the completed 2024 ESPN fixture season.
    reader = FixtureReader(FIXTURE_ROOT)
    _managers, team_seasons = load_team_seasons(reader)

    # When: supported record rows are derived from actual standings and box scores.
    rows = record_rows(reader, team_seasons, (2024,))
    rows_by_category = {row.category: row for row in rows}

    # Then: weekly, matchup, and season records are exposed without guessed categories.
    assert {
        "highest_weekly_score",
        "lowest_weekly_score",
        "closest_matchup",
        "largest_matchup",
        "best_season_record",
        "worst_season_record",
        "most_season_points",
    } <= set(rows_by_category)
    assert "championships" not in rows_by_category
    assert "playoff_appearances" not in rows_by_category
    assert rows_by_category["highest_weekly_score"].value > rows_by_category[
        "lowest_weekly_score"
    ].value
    assert rows_by_category["closest_matchup"].value < rows_by_category[
        "largest_matchup"
    ].value


def test_head_to_head_pairs_include_matchup_rollups() -> None:
    # Given: the completed 2024 ESPN fixture season.
    reader = FixtureReader(FIXTURE_ROOT)
    _managers, team_seasons = load_team_seasons(reader)

    # When: head-to-head artifacts are derived from box-score matchups.
    pairs = head_to_head_pairs(reader, team_seasons, (2024,))
    pair = pairs[0]

    # Then: each pair exposes matchups plus aggregate head-to-head facts.
    assert pair.matchups
    assert pair.manager_a_key < pair.manager_b_key
    assert pair.wins_a + pair.wins_b + pair.ties == len(pair.matchups)
    assert pair.average_score_a > 0
    assert pair.average_score_b > 0
    assert pair.biggest_win_margin >= 0
    assert pair.current_streak
    assert pair.playoff_wins_a + pair.playoff_wins_b + pair.playoff_ties <= len(
        pair.matchups
    )


def test_luck_strength_rows_caveat_partial_seasons() -> None:
    # Given: a partial season is included in the source set.
    reader = FixtureReader(FIXTURE_ROOT)
    seasons = reader.seasons()
    partial_seasons = tuple(season.season for season in seasons if season.is_partial)
    _managers, team_seasons = load_team_seasons(reader)

    # When: actual records are compared with all possible weekly schedules.
    rows = luck_strength_rows(reader, team_seasons, partial_seasons)

    # Then: the rows are computed but explicitly caveated as partial.
    assert rows
    assert all(row.possible_games > 0 for row in rows)
    assert all(row.caveats for row in rows)
    assert any("partial season" in caveat for row in rows for caveat in row.caveats)
