from __future__ import annotations

from pathlib import Path

from mygm_worker.analytics.adp import load_adp_index
from mygm_worker.analytics.draft import draft_grades, season_drafts
from mygm_worker.analytics.identity import load_team_seasons
from mygm_worker.analytics.lineup_efficiency import lineup_efficiency_rows
from mygm_worker.analytics.manager_value import manager_value
from mygm_worker.analytics.ratings import RATING_WEIGHTS_V3, gm_ratings_v3
from mygm_worker.analytics.reader import FixtureReader
from mygm_worker.analytics.vor import build_vor_model, position_for_lookup_entry

FIXTURE_ROOT = Path(__file__).parents[4] / "espn_exports" / "league_18254195"


def _drafts():  # noqa: ANN202 - test helper
    reader = FixtureReader(FIXTURE_ROOT)
    managers, team_seasons = load_team_seasons(reader)
    vor_model = build_vor_model(reader)
    positions = {
        int(pid): position_for_lookup_entry(player)
        for pid, player in reader.player_lookup().items()
        if isinstance(player, dict)
    }
    return season_drafts(
        reader,
        managers,
        team_seasons,
        vor_model=vor_model,
        position_by_player=positions,
        adp_index=load_adp_index(),
    )


def test_picks_carry_vor_surplus_and_expected_curve() -> None:
    drafts = _drafts()
    picks = [pick for draft in drafts for pick in draft.picks]
    assert picks
    # surplus == season_vor - expected_vor for every pick.
    for pick in picks:
        assert pick.surplus == round(pick.season_vor - pick.expected_vor, 4)


def test_expected_curve_is_richer_early_than_late() -> None:
    drafts = _drafts()
    all_picks = [pick for draft in drafts for pick in draft.picks]
    early = [pick.expected_vor for pick in all_picks if pick.overall_pick <= 10]
    late = [pick.expected_vor for pick in all_picks if pick.overall_pick >= 120]
    assert early
    assert late
    # Early-round slots are expected to return more value than late-round slots.
    assert sum(early) / len(early) > sum(late) / len(late)


def test_known_late_steal_has_large_positive_surplus() -> None:
    drafts = _drafts()
    by_season = {draft.season: draft for draft in drafts}
    jefferson = next(
        pick
        for pick in by_season[2020].picks
        if pick.player_name == "Justin Jefferson" and pick.overall_pick == 154
    )
    # A 154th pick who produced a strong season is a big slot-relative steal: his VOR
    # towers over the deeply-negative expectation for that slot.
    assert jefferson.surplus > 40.0
    assert jefferson.surplus == round(jefferson.season_vor - jefferson.expected_vor, 4)


def test_2025_grades_without_adp_degrade_gracefully() -> None:
    drafts = _drafts()
    by_season = {draft.season: draft for draft in drafts}
    picks_2025 = by_season[2025].picks
    assert picks_2025
    # 2025 has no vendored ADP: reach flavor is blank, but the slot-based surplus is live.
    assert all(pick.adp is None for pick in picks_2025)
    assert any(pick.surplus != 0.0 for pick in picks_2025)


def test_draft_grades_exclude_keepers_and_aggregate_career() -> None:
    drafts = _drafts()
    included = tuple(sorted({d.season for d in drafts if not d.is_partial}))
    grades = draft_grades(drafts, included)
    assert grades.career_surplus
    assert grades.best_pick_by_manager
    # Keepers never surface as a manager's best/worst graded pick.
    graded_picks = set(grades.best_pick_by_manager.values()) | set(
        grades.worst_pick_by_manager.values()
    )
    assert all(not pick.keeper for pick in graded_picks)


def test_v3_rating_has_six_weighted_components() -> None:
    reader = FixtureReader(FIXTURE_ROOT)
    managers, team_seasons = load_team_seasons(reader)
    vor_model = build_vor_model(reader)
    positions = {
        int(pid): position_for_lookup_entry(player)
        for pid, player in reader.player_lookup().items()
        if isinstance(player, dict)
    }
    drafts = season_drafts(
        reader, managers, team_seasons, vor_model=vor_model, position_by_player=positions
    )
    value = manager_value(reader, managers, team_seasons, vor_model=vor_model)
    lineup_rows = lineup_efficiency_rows(reader, managers, team_seasons)
    included = tuple(sorted({d.season for d in drafts if not d.is_partial}))
    grades = draft_grades(drafts, included)
    ratings = gm_ratings_v3(
        team_seasons=team_seasons,
        included_seasons=included,
        season_values=value.season_values,
        lineup_rows=lineup_rows,
        draft_surplus=grades.surplus_by_manager_season,
    )
    assert ratings
    assert round(sum(RATING_WEIGHTS_V3.values()), 6) == 1.0
    career = [rating for rating in ratings if rating.season is None]
    assert career
    for rating in career:
        assert set(rating.raw_components) == set(RATING_WEIGHTS_V3)
        assert 0.0 <= rating.final_score <= 100.0
