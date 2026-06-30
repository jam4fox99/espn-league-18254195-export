from __future__ import annotations

import json
from typing import TYPE_CHECKING

from mygm_worker.analytics.injuries import InjuryIndex, load_injury_index
from mygm_worker.analytics.nfl_schedule import ScheduleIndex, load_schedule_index
from mygm_worker.analytics.player_badges import (
    BADGES,
    _badge_scores,
    _cv,
    _matchup_swing,
    _Percentiles,
    _percentiles,
    _pick_badge,
    _PlayerStats,
)

if TYPE_CHECKING:
    from pathlib import Path


# --------------------------------------------------------------- statistics


def test_percentiles_midrank_orders_and_ties() -> None:
    pct = _percentiles({1: 1.0, 2: 2.0, 3: 3.0})
    assert pct[1] < pct[2] < pct[3]
    assert pct[1] == 0.5 / 3
    assert _percentiles({1: 5.0, 2: 5.0}) == {1: 0.5, 2: 0.5}


def test_percentiles_is_key_type_agnostic() -> None:
    # Used with int player ids and str opponent codes alike.
    pct = _percentiles({"SF": 10.0, "KC": 30.0})
    assert pct["KC"] > pct["SF"]


def test_cv_is_zero_without_spread_or_signal() -> None:
    assert _cv([10.0, 10.0, 10.0]) == 0.0  # no spread
    assert _cv([5.0]) == 0.0  # too few games
    assert _cv([0.0, 0.0]) == 0.0  # no mean
    assert _cv([0.0, 20.0, 10.0]) > 0.0  # real volatility


# ------------------------------------------------------------- matchup math


def test_matchup_swing_needs_both_splits() -> None:
    # Only easy weeks (rank >= 0.6) → no tough sample → 0.
    only_easy = [(20.0, 0.9), (18.0, 0.8), (22.0, 0.7), (19.0, 0.65)]
    assert _matchup_swing(only_easy) == 0.0


def test_matchup_swing_measures_easy_minus_tough() -> None:
    pairs = [
        *[(30.0, 0.9) for _ in range(4)],  # easy weeks: big scores
        *[(10.0, 0.1) for _ in range(4)],  # tough weeks: small scores
    ]
    swing = _matchup_swing(pairs)
    # easy mean 30, tough mean 10, overall 20 → (30-10)/20 = 1.0.
    assert swing == 1.0


# ----------------------------------------------------- badge assignment


def _pct(**overrides: dict[int, float]) -> _Percentiles:
    base: dict[str, dict[int, float]] = {
        "mean": {1: 0.5},
        "cv": {1: 0.5},
        "td": {1: 0.5},
        "injury": {1: 0.5},
        "swing": {1: 0.5},
        "ypr": {1: 0.5},
        "recpg": {1: 0.5},
    }
    base.update(overrides)
    return _Percentiles(**base)  # type: ignore[arg-type]


def _stats(position: str = "WR") -> _PlayerStats:
    return _PlayerStats(player_id=1, name="Test Player", position=position)


def test_high_volatility_is_boom_or_bust() -> None:
    scores = _badge_scores(
        _stats(), _pct(cv={1: 0.9}), td={1: 0.0}, injury={1: 0.0}, swing={1: 0.0}, recpg={}
    )
    assert max(scores, key=lambda b: scores[b]) == "Boom or Bust"


def test_low_volatility_high_output_is_elite_consistent() -> None:
    badge = _pick_badge(
        _stats(),
        _pct(cv={1: 0.1}, mean={1: 0.9}),
        td={1: 0.0},
        injury={1: 0.0},
        swing={1: 0.0},
        recpg={},
    )
    assert badge == "Elite Consistent"


def test_low_volatility_mid_output_is_high_floor() -> None:
    badge = _pick_badge(
        _stats(),
        _pct(cv={1: 0.1}, mean={1: 0.4}),
        td={1: 0.0},
        injury={1: 0.0},
        swing={1: 0.0},
        recpg={},
    )
    assert badge == "High Floor"


def test_high_reception_volume_low_yardage_is_screen_merchant() -> None:
    scores = _badge_scores(
        _stats(),
        _pct(cv={1: 0.5}, recpg={1: 0.9}, ypr={1: 0.1}),
        td={1: 0.0},
        injury={1: 0.0},
        swing={1: 0.0},
        recpg={1: 6.0},  # well above the volume gate
    )
    assert "Screen Merchant" in scores
    assert max(scores, key=lambda b: scores[b]) == "Screen Merchant"


def test_high_yards_per_reception_is_explosive() -> None:
    scores = _badge_scores(
        _stats(),
        _pct(cv={1: 0.5}, ypr={1: 0.95}, recpg={1: 0.5}),
        td={1: 0.0},
        injury={1: 0.0},
        swing={1: 0.0},
        recpg={1: 4.0},
    )
    assert scores.get("Explosive") == 0.95


def test_touchdown_reliance_gates_on_fraction() -> None:
    no_badge = _badge_scores(
        _stats(), _pct(td={1: 0.9}), td={1: 0.10}, injury={1: 0.0}, swing={1: 0.0}, recpg={}
    )
    assert "TD Dependent" not in no_badge  # 10% of points from TDs — not reliant
    fires = _badge_scores(
        _stats(), _pct(td={1: 0.9}), td={1: 0.45}, injury={1: 0.0}, swing={1: 0.0}, recpg={}
    )
    assert fires["TD Dependent"] == 0.9


def test_quarterbacks_never_get_td_dependent() -> None:
    # QB scoring is inherently TD-heavy, so the badge would not be distinctive.
    qb = _badge_scores(
        _stats("QB"), _pct(td={1: 0.95}), td={1: 0.60}, injury={1: 0.0}, swing={1: 0.0}, recpg={}
    )
    assert "TD Dependent" not in qb


def test_elite_is_reserved_for_top_quartile_output() -> None:
    # Low volatility + merely above-average output is High Floor, not Elite.
    steady = _pick_badge(
        _stats(),
        _pct(cv={1: 0.1}, mean={1: 0.65}),
        td={1: 0.0},
        injury={1: 0.0},
        swing={1: 0.0},
        recpg={},
    )
    assert steady == "High Floor"
    # Low volatility + top-quartile output earns Elite.
    elite = _pick_badge(
        _stats(),
        _pct(cv={1: 0.1}, mean={1: 0.85}),
        td={1: 0.0},
        injury={1: 0.0},
        swing={1: 0.0},
        recpg={},
    )
    assert elite == "Elite Consistent"


def test_injury_and_matchup_gate_on_real_thresholds() -> None:
    healthy = _badge_scores(
        _stats(), _pct(injury={1: 0.9}), td={1: 0.0}, injury={1: 0.5}, swing={1: 0.0}, recpg={}
    )
    assert "Injury Risk" not in healthy  # 0.5 weighted weeks/season is below the gate
    injured = _badge_scores(
        _stats(), _pct(injury={1: 0.9}), td={1: 0.0}, injury={1: 2.5}, swing={1: 0.0}, recpg={}
    )
    assert injured["Injury Risk"] == 0.9
    matchup = _badge_scores(
        _stats(), _pct(swing={1: 0.8}), td={1: 0.0}, injury={1: 0.0}, swing={1: 0.5}, recpg={}
    )
    assert matchup["Matchup Based"] == 0.8


def test_badge_set_is_the_canonical_eight() -> None:
    # Mirror of the web styling map (apps/web/lib/images.ts PLAYER_BADGE_STYLES);
    # renaming a badge must update both, so both sides assert the exact set.
    assert set(BADGES) == {
        "Elite Consistent",
        "High Floor",
        "Boom or Bust",
        "Explosive",
        "TD Dependent",
        "Screen Merchant",
        "Matchup Based",
        "Injury Risk",
    }
    assert len(BADGES) == 8  # no duplicates


# --------------------------------------------------------- vendored loaders


def test_load_schedule_index_joins_and_aliases(tmp_path: Path) -> None:
    (tmp_path / "schedule_2023.json").write_text(
        json.dumps(
            {"season": 2023, "byTeam": {"LA": {"1": "SEA", "2": "SF"}, "SEA": {"1": "LA"}}}
        ),
        encoding="utf-8",
    )
    index = load_schedule_index(tmp_path)
    assert index.seasons == (2023,)
    assert index.opponent(2023, "SEA", 1) == "LA"
    # ESPN's "LAR" aliases to nflverse "LA" so a proTeamId-derived code still joins.
    assert index.opponent(2023, "LAR", 1) == "SEA"
    assert index.opponent(2023, "LA", 9) == ""  # bye / unknown week


def test_schedule_index_missing_season_is_empty() -> None:
    index = ScheduleIndex(by_season={})
    assert index.opponent(2023, "KC", 1) == ""
    assert not index.has_season(2023)


def test_load_injury_index_sums_weighted_burden(tmp_path: Path) -> None:
    (tmp_path / "injuries_2022.json").write_text(
        json.dumps(
            {
                "season": 2022,
                "players": {"alvinkamara": {"out": 2, "doubtful": 0, "questionable": 4}},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "injuries_2023.json").write_text(
        json.dumps(
            {
                "season": 2023,
                "players": {"alvinkamara": {"out": 1, "doubtful": 1, "questionable": 0}},
            }
        ),
        encoding="utf-8",
    )
    index = load_injury_index(tmp_path)
    # 2022: 2*1.0 + 4*0.25 = 3.0; 2023: 1*1.0 + 1*0.7 = 1.7.
    assert index.burden("Alvin Kamara", {2022, 2023}) == 4.7
    assert index.burden("Alvin Kamara", {2023}) == 1.7  # scoped to the asked season
    assert index.burden("Alvin Kamara", {2020}) == 0.0  # no data that season
    assert index.burden("Nobody", {2022}) == 0.0
    # Both vendored seasons register as covered; an unseen season does not.
    assert index.covered_seasons == frozenset({2022, 2023})
    assert index.covered_count({2022, 2023, 2026}) == 2


def test_load_injury_index_skips_a_malformed_season_atomically(tmp_path: Path) -> None:
    (tmp_path / "injuries_2022.json").write_text(
        json.dumps(
            {
                "season": 2022,
                "players": {"alvinkamara": {"out": 3, "doubtful": 0, "questionable": 0}},
            }
        ),
        encoding="utf-8",
    )
    # 2023's players map has a non-object entry, so parsing the file raises mid-loop.
    (tmp_path / "injuries_2023.json").write_text(
        json.dumps({"season": 2023, "players": {"alvinkamara": "not-an-object"}}), encoding="utf-8"
    )
    index = load_injury_index(tmp_path)
    # 2023 is dropped entirely — neither its burden nor its covered-season slips in,
    # so burden and covered_seasons can never disagree.
    assert index.covered_seasons == frozenset({2022})
    assert index.burden("Alvin Kamara", {2022, 2023}) == 3.0


def test_injury_index_normalizes_name() -> None:
    index = InjuryIndex(
        burden_by_name={"patrickmahomes": {2023: 2.0}}, covered_seasons=frozenset({2023})
    )
    assert index.burden("Patrick Mahomes II", {2023}) == 2.0
    assert index.covered_count({2023, 2024}) == 1
