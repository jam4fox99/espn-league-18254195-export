from __future__ import annotations

from pathlib import Path

from mygm_worker.analytics.reader import FixtureReader
from mygm_worker.analytics.vor import VorModel, build_vor_model, position_for_lookup_entry

FIXTURE_ROOT = Path(__file__).parents[4] / "espn_exports" / "league_18254195"


def _model() -> VorModel:
    return build_vor_model(FixtureReader(FIXTURE_ROOT))


def test_value_for_weeks_charges_replacement_per_active_week() -> None:
    # Given: a model with a known QB replacement baseline of 18 ppw.
    model = VorModel(replacement_per_week={(2024, "QB"): 18.0}, starter_demand={(2024, "QB"): 10})

    # When: a player scores 30, 6, and 18 across three active weeks.
    vor, weeks = model.value_for_weeks(2024, "QB", {"1": 30.0, "2": 6.0, "3": 18.0})

    # Then: VOR sums (points - replacement) over exactly those weeks.
    assert weeks == 3
    assert vor == (30 - 18) + (6 - 18) + (18 - 18)


def test_window_value_only_counts_weeks_in_range() -> None:
    model = VorModel(replacement_per_week={(2024, "RB"): 10.0}, starter_demand={(2024, "RB"): 20})
    weekly = {"1": 20.0, "5": 20.0, "9": 20.0}

    assert model.window_value(2024, "RB", weekly, start_week=5, end_week=17) == round(20.0, 4)


def test_unknown_position_has_zero_replacement() -> None:
    model = VorModel(replacement_per_week={}, starter_demand={})
    vor, weeks = model.value_for_weeks(2024, "QB", {"1": 25.0})
    assert (vor, weeks) == (25.0, 1)


def test_starter_demand_reflects_one_qb_league_shape() -> None:
    # Given: league 18254195 is a 10-team, one-QB league with RB/WR/TE flex.
    model = _model()

    # When/Then: QB demand equals the team count, and RB/WR demand is much deeper.
    qb_demand = model.starter_demand[(2024, "QB")]
    assert qb_demand == 10
    assert model.starter_demand[(2024, "RB")] > qb_demand
    assert model.starter_demand[(2024, "WR")] > qb_demand


def test_qb_replacement_lands_near_eighteen_ppg() -> None:
    # The whole point of VOR: the one-QB replacement bar sits high (~18-21 PPG).
    model = _model()
    for season in (2023, 2024, 2025):
        replacement = model.replacement(season, "QB")
        assert 15.0 <= replacement <= 22.0, (season, replacement)


def test_stud_rb_outvalues_elite_qb_over_a_full_season() -> None:
    # The core invariant: a stud RB must out-rank an elite QB in season VOR, even though
    # the QB scores more raw points — otherwise QBs inflate trade/waiver value.
    reader = FixtureReader(FIXTURE_ROOT)
    model = build_vor_model(reader)
    players = reader.player_lookup()

    best: dict[str, float] = {}
    for player in players.values():
        if not isinstance(player, dict):
            continue
        position = position_for_lookup_entry(player)
        if position not in {"QB", "RB"}:
            continue
        details = player.get("weekly_details")
        if not isinstance(details, dict):
            continue
        weeks_2024 = details.get("2024")
        if not isinstance(weeks_2024, dict):
            continue
        points = {
            week: detail.get("points", 0.0)
            for week, detail in weeks_2024.items()
            if isinstance(detail, dict) and (detail.get("appliedStats") or detail.get("points"))
        }
        vor, _ = model.value_for_weeks(2024, position, points)
        best[position] = max(best.get(position, float("-inf")), vor)

    assert best["RB"] > best["QB"]
