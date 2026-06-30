from __future__ import annotations

import collections
import itertools
from pathlib import Path

from mygm_worker.analytics.identity import load_team_seasons
from mygm_worker.analytics.reader import FixtureReader
from mygm_worker.analytics.roster_fit import build_fit_index
from mygm_worker.analytics.trade_events import trade_event_rows
from mygm_worker.analytics.trade_grades import (
    GRADE_ORDER,
    grade_for_composite,
    grade_trade_event,
    value_score,
)
from mygm_worker.analytics.vor import build_vor_model, position_for_lookup_entry

FIXTURE_ROOT = Path(__file__).parents[4] / "espn_exports" / "league_18254195"


def test_value_score_is_saturating_and_centered() -> None:
    # Even trade -> 0.5; bigger edges climb but saturate (no runaway).
    assert value_score(0.0) == 0.5
    assert value_score(-40.0) < 0.5 < value_score(40.0)
    big = value_score(200.0)
    bigger = value_score(400.0)
    assert big > 0.9
    # The +200 vs +400 gap is tiny — both near the top, which kills bimodality.
    assert bigger - big < 0.05


def test_grade_for_composite_is_monotonic() -> None:
    assert grade_for_composite(0.95) == "A+"
    assert grade_for_composite(0.5) in {"B-", "C+", "B"}
    assert grade_for_composite(0.0) == "F"
    grades = [grade_for_composite(value / 100) for value in range(100, -1, -1)]
    ranks = [GRADE_ORDER.index(grade) for grade in grades]
    # As composite falls, the grade index moves monotonically toward F (never improves).
    assert all(later >= earlier for earlier, later in itertools.pairwise(ranks))


def _grade_all() -> list[str]:
    reader = FixtureReader(FIXTURE_ROOT)
    _, team_seasons = load_team_seasons(reader)
    team_lookup = {(row.season, row.team_id): row.manager_key for row in team_seasons}
    vor_model = build_vor_model(reader)
    fit_index = build_fit_index(reader, team_seasons)
    position_by_player = {
        int(pid): position_for_lookup_entry(player)
        for pid, player in reader.player_lookup().items()
        if isinstance(player, dict)
    }
    grades: list[str] = []
    for row in trade_event_rows(reader):
        graded = grade_trade_event(
            row,
            vor_model=vor_model,
            position_by_player=position_by_player,
            fit_index=fit_index,
            team_lookup=team_lookup,
        )
        if graded is not None:
            grades.extend(side.grade for side in graded.sides)
    return grades


def test_trade_grade_distribution_is_bell_shaped() -> None:
    # The headline goal: A+ and F are rare, the B/C middle is fat.
    grades = _grade_all()
    assert len(grades) >= 100
    counts = collections.Counter(grades)
    total = len(grades)
    families = collections.Counter(grade[0] for grade in grades)

    assert counts["A+"] / total <= 0.07
    assert counts["F"] / total <= 0.07
    middle = (families["B"] + families["C"]) / total
    assert 0.50 <= middle <= 0.68, middle
    # Every side gets a real letter from the ladder.
    assert set(grades) <= set(GRADE_ORDER)


def test_full_rescue_lifts_a_points_loss_that_fills_a_need() -> None:
    # A side that loses on raw VOR but fills a genuine need should not bottom out: fit
    # pulls its composite up out of the F/D cellar.
    reader = FixtureReader(FIXTURE_ROOT)
    _, team_seasons = load_team_seasons(reader)
    team_lookup = {(row.season, row.team_id): row.manager_key for row in team_seasons}
    vor_model = build_vor_model(reader)
    fit_index = build_fit_index(reader, team_seasons)
    position_by_player = {
        int(pid): position_for_lookup_entry(player)
        for pid, player in reader.player_lookup().items()
        if isinstance(player, dict)
    }
    rescued = False
    for row in trade_event_rows(reader):
        graded = grade_trade_event(
            row,
            vor_model=vor_model,
            position_by_player=position_by_player,
            fit_index=fit_index,
            team_lookup=team_lookup,
        )
        if graded is None:
            continue
        for side in graded.sides:
            if side.net_vor < -20 and side.needs_filled and side.grade not in {"F", "D-"}:
                rescued = True
    assert rescued
