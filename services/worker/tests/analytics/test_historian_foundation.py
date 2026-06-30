from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from mygm_worker.analytics.career import ManagerCareer, manager_careers
from mygm_worker.analytics.draft import SeasonDraft, season_drafts
from mygm_worker.analytics.identity import load_team_seasons
from mygm_worker.analytics.lineup_efficiency import (
    LineupEntry,
    LineupSeasonRow,
    lineup_efficiency_rows,
    optimal_lineup_points,
)
from mygm_worker.analytics.manager_value import ManagerValueResult, manager_value
from mygm_worker.analytics.models import ManagerIdentity, TeamSeason
from mygm_worker.analytics.player_leaderboards import player_leaderboards
from mygm_worker.analytics.ratings import gm_ratings_v2
from mygm_worker.analytics.reader import FixtureReader
from mygm_worker.analytics.report import analyze_fixture
from mygm_worker.analytics.rivalries import RivalryMatrix, rivalry_matrix
from mygm_worker.analytics.standings import SeasonStandings, TeamStanding, season_standings

FIXTURE_ROOT = Path(__file__).parents[4] / "espn_exports" / "league_18254195"


# --- Fast unit tests for the pure solvers -----------------------------------


def test_optimal_lineup_points_promotes_bench_and_fills_flex_and_skips_ir() -> None:
    # Given: a QB, two startable RBs, a higher-scoring benched RB, and an IR stash.
    entries = [
        LineupEntry(points=20.0, eligible_slots=frozenset({0}), lineup_slot_id=0),  # QB
        LineupEntry(points=15.0, eligible_slots=frozenset({2, 23}), lineup_slot_id=2),  # RB start
        LineupEntry(points=10.0, eligible_slots=frozenset({2, 23}), lineup_slot_id=20),  # RB bench
        LineupEntry(points=12.0, eligible_slots=frozenset({2, 23}), lineup_slot_id=20),  # RB bench
        LineupEntry(points=99.0, eligible_slots=frozenset({2, 23}), lineup_slot_id=21),  # IR
    ]
    starting_slots = {0: 1, 2: 1, 23: 1}

    # When: the optimal legal lineup is computed.
    optimal = optimal_lineup_points(entries, starting_slots)

    # Then: QB(20) + best RB(15) + next-best eligible into FLEX(12); IR is never started.
    assert optimal == pytest.approx(47.0)


def test_optimal_lineup_points_returns_zero_without_startable_players() -> None:
    entries = [LineupEntry(points=50.0, eligible_slots=frozenset({20}), lineup_slot_id=20)]
    assert optimal_lineup_points(entries, {0: 1}) == 0.0


def test_career_detects_consecutive_dynasty_and_drought_eras() -> None:
    # Given: one manager whose ranks form a 2020-2021 dynasty and a 2023-2024 drought.
    ranks = {2020: 1, 2021: 3, 2022: 5, 2023: 9, 2024: 10, 2025: 6}
    standings = tuple(_standings_for(season, rank) for season, rank in ranks.items())
    managers = {
        "espn-owner:m": ManagerIdentity("espn-owner:m", "Test GM", "m", is_unresolved=False)
    }

    # When: careers are derived with no rating context.
    careers = manager_careers(standings, managers, {}, {}, tuple(ranks))
    career = next(item for item in careers if item.manager_key == "espn-owner:m")

    # Then: exactly one dynasty era and one drought era are detected with correct spans.
    eras = {(era.kind, era.start_season, era.end_season) for era in career.eras}
    assert ("dynasty", 2020, 2021) in eras
    assert ("drought", 2023, 2024) in eras
    assert career.titles == 1
    assert career.best_finish == 1
    assert career.worst_finish == 10


def _standings_for(season: int, rank: int) -> SeasonStandings:
    team = TeamStanding(
        season=season,
        team_id=1,
        manager_key="espn-owner:m",
        display_name="Test GM",
        team_name="Test Team",
        rank_final=rank,
        playoff_seed=rank,
        made_playoffs=rank <= 6,
        is_champion=rank == 1,
        is_runner_up=rank == 2,
        wins=10 - rank,
        losses=rank,
        ties=0,
        points_for=1500.0 - rank,
        points_against=1400.0,
    )
    # Pad to a 10-team league so the bottom-third cutoff resolves to ranks 8-10.
    others = tuple(
        TeamStanding(
            season=season,
            team_id=team_id,
            manager_key=f"espn-owner:other-{team_id}",
            display_name=f"Other {team_id}",
            team_name=f"Team {team_id}",
            rank_final=team_id,
            playoff_seed=team_id,
            made_playoffs=team_id <= 6,
            is_champion=False,
            is_runner_up=False,
            wins=0,
            losses=0,
            ties=0,
            points_for=0.0,
            points_against=0.0,
        )
        for team_id in range(2, 11)
    )
    return SeasonStandings(
        season=season,
        is_partial=False,
        playoff_team_count=6,
        champion_manager_key=None,
        champion_display_name=None,
        champion_team_name=None,
        runner_up_manager_key=None,
        runner_up_display_name=None,
        standings=(team, *others),
    )


# --- Characterization tests against the real ESPN fixture -------------------


@dataclass(frozen=True, slots=True)
class _Historian:
    standings: tuple[SeasonStandings, ...]
    drafts: tuple[SeasonDraft, ...]
    lineup_rows: tuple[LineupSeasonRow, ...]
    value: ManagerValueResult
    matrix: RivalryMatrix
    careers: tuple[ManagerCareer, ...]
    team_seasons: list[TeamSeason]
    included: tuple[int, ...]


@pytest.fixture(scope="module")
def historian() -> _Historian:
    reader = FixtureReader(FIXTURE_ROOT)
    summary = analyze_fixture(FIXTURE_ROOT)
    managers, team_seasons = load_team_seasons(reader)
    included = summary.career_included_seasons
    standings = season_standings(reader, managers, team_seasons)
    season_rating = {
        (r.manager_key, r.season): r.final_score
        for r in summary.gm_ratings
        if r.season is not None
    }
    career_rating = {
        r.manager_key: r.final_score for r in summary.gm_ratings if r.season is None
    }
    return _Historian(
        standings=standings,
        drafts=season_drafts(reader, managers, team_seasons),
        lineup_rows=lineup_efficiency_rows(reader, managers, team_seasons),
        value=manager_value(reader, managers, team_seasons),
        matrix=rivalry_matrix(reader, managers, team_seasons, included),
        careers=manager_careers(standings, managers, season_rating, career_rating, included),
        team_seasons=team_seasons,
        included=included,
    )


def test_player_leaderboards_rank_started_scoring_with_attribution() -> None:
    reader = FixtureReader(FIXTURE_ROOT)
    managers, team_seasons = load_team_seasons(reader)
    boards = player_leaderboards(reader, managers, team_seasons)

    assert len(boards.top_weeks) == 15
    assert len(boards.top_seasons) == 15
    # Boards are ranked by points, descending.
    week_points = [row.points for row in boards.top_weeks]
    assert week_points == sorted(week_points, reverse=True)
    season_points = [row.points for row in boards.top_seasons]
    assert season_points == sorted(season_points, reverse=True)
    # The top weekly mark is a real, attributed, high-scoring performance.
    top_week = boards.top_weeks[0]
    assert top_week.player_name
    assert top_week.display_name
    assert top_week.points > 50.0
    # Season totals only credit players with a meaningful sample of starts.
    assert all(row.weeks >= 4 for row in boards.top_seasons)


def test_standings_extract_champions_and_skip_partial_season(historian: _Historian) -> None:
    by_season = {row.season: row for row in historian.standings}
    assert by_season[2021].champion_display_name == "Charlie Kayne"
    assert by_season[2023].champion_display_name == "levi reed"
    assert by_season[2026].is_partial is True
    assert by_season[2026].champion_manager_key is None
    # Every completed season crowns exactly one champion.
    completed = [row for row in historian.standings if not row.is_partial]
    assert all(row.champion_manager_key is not None for row in completed)


def test_draft_identifies_known_steal_and_bust(historian: _Historian) -> None:
    by_season = {row.season: row for row in historian.drafts}
    steal_2020 = by_season[2020].best_steal
    assert steal_2020 is not None
    assert steal_2020.player_name == "Justin Jefferson"
    assert steal_2020.overall_pick == 154
    assert steal_2020.steal_value > 100

    bust_2024 = by_season[2024].biggest_bust
    assert bust_2024 is not None
    assert bust_2024.overall_pick == 1
    assert bust_2024.steal_value < 0


def test_manager_value_tracks_trade_partners_and_waiver_leader(historian: _Historian) -> None:
    value = historian.value
    trade_by_manager = {ledger.display_name: ledger for ledger in value.trade_ledgers}
    gruber = trade_by_manager["Jordan Gruber"]
    assert gruber.trade_count > 0
    assert gruber.partners  # favorite trade partners are populated
    assert gruber.best_trade is not None
    # The trade-summary receipt is the manager's OWN side only (regression: both sides
    # used to list the same acquired players).
    best_summary = (gruber.best_trade or {}).get("summary")
    worst_summary = (gruber.worst_trade or {}).get("summary")
    assert best_summary != worst_summary

    # Trade + waiver value are now measured in VOR, so the leaders reflect value over
    # replacement rather than raw points.
    trade_leader = max(value.trade_ledgers, key=lambda ledger: ledger.net_points)
    assert trade_leader.display_name == "Gus Koven"
    assert trade_leader.net_points > 0

    waiver_leader = max(value.waiver_ledgers, key=lambda ledger: ledger.net_points)
    assert waiver_leader.display_name == "Julian Sacks"
    assert waiver_leader.net_points > 0


def test_rivalries_resolve_nemesis_and_favorite(historian: _Historian) -> None:
    summaries = {row.display_name: row for row in historian.matrix.summaries}
    jake = summaries["Jake Milken"]
    assert jake.favorite is not None
    assert jake.favorite.opponent_display_name == "Ethan Lee"
    assert jake.favorite.losses == 0
    assert jake.nemesis is not None
    assert jake.nemesis.win_pct <= jake.favorite.win_pct


def test_lineup_efficiency_rows_are_plausible(historian: _Historian) -> None:
    rows = historian.lineup_rows
    assert len(rows) >= 50
    for row in rows:
        assert 0.0 <= row.avg_efficiency <= 100.0
        assert row.optimal_points >= row.started_points
        assert row.bench_points >= 0.0


def test_careers_roll_up_titles_and_eras(historian: _Historian) -> None:
    careers = {career.display_name: career for career in historian.careers}
    levi = careers["levi reed"]
    assert levi.titles == 1
    assert levi.seasons_played == 6
    assert any(era.kind == "dynasty" for era in levi.eras)


def test_v2_rating_uses_real_components_without_luck(historian: _Historian) -> None:
    ratings = gm_ratings_v2(
        team_seasons=historian.team_seasons,
        included_seasons=historian.included,
        season_values=historian.value.season_values,
        lineup_rows=historian.lineup_rows,
    )
    season_ratings = [r for r in ratings if r.season is not None]
    career_ratings = [r for r in ratings if r.season is None]
    assert season_ratings
    assert career_ratings

    expected_components = {"tradeValue", "waiverValue", "lineupEfficiency", "recordAndPoints"}
    for rating in ratings:
        assert rating.formula_version == "mygm-historian-v2"
        assert set(rating.raw_components) == expected_components
        assert "luckAdjusted" not in rating.raw_components
        assert 0.0 <= rating.final_score <= 100.0

    # Career score is the mean of that manager's season scores.
    by_key: dict[str, list[float]] = {}
    for rating in season_ratings:
        by_key.setdefault(rating.manager_key, []).append(rating.final_score)
    multi = next(r for r in career_ratings if len(by_key.get(r.manager_key, [])) >= 2)
    seasons = by_key[multi.manager_key]
    assert multi.final_score == pytest.approx(sum(seasons) / len(seasons), abs=0.01)
