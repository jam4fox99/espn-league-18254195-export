from __future__ import annotations

import json
from pathlib import Path

from mygm_worker.analytics.identity import (
    load_team_seasons,
    manager_rows,
    manager_summary,
)
from mygm_worker.analytics.models import (
    AcquisitionAnalytics,
    JsonValue,
    TeamSeason,
    TradeAnalytics,
)
from mygm_worker.analytics.ratings import (
    RATING_WEIGHTS,
    gm_ratings,
    manager_rating_rows,
)
from mygm_worker.analytics.reader import FixtureReader


def test_manager_components_use_owner_keys_aliases_and_approved_formula() -> None:
    # Given: two owner-backed teams across one completed season.
    team_seasons = [
        _team_season(team_id=1, manager_key="espn-owner:owner-1", points_for=1100.0),
        _team_season(team_id=2, manager_key="espn-owner:owner-2", points_for=1000.0),
    ]

    # When: GM ratings and helper rows are derived.
    ratings = gm_ratings(
        team_seasons=team_seasons,
        included_seasons=(2024,),
        trade_summary=_trade_summary(),
        acquisition_summary=_acquisition_summary(),
    )
    rows = manager_rating_rows(team_seasons=team_seasons, ratings=ratings)

    # Then: the approved component contract is present for season and all-time rows.
    assert RATING_WEIGHTS == {
        "tradePerformance": 0.35,
        "waiverPerformance": 0.35,
        "recordAndPoints": 0.20,
        "luckAdjusted": 0.10,
    }
    assert {rating.season for rating in ratings} == {2024, None}
    for rating in ratings:
        assert rating.manager_key.startswith("espn-owner:")
        assert rating.raw_components.keys() == RATING_WEIGHTS.keys()
        assert rating.normalized_components.keys() == RATING_WEIGHTS.keys()
        assert "draft" not in {key.lower() for key in rating.raw_components}

    row = next(item for item in rows if item["managerKey"] == "espn-owner:owner-1")
    assert row["scoreEligible"] is True
    assert row["aliases"] == [{"season": 2024, "teamId": 1, "teamName": "Team 1"}]


def test_unresolved_manager_is_ineligible_and_visible_in_helper_output(
    tmp_path: Path,
) -> None:
    # Given: an ESPN fixture with one team missing owner data.
    fixture_root = _write_minimal_fixture(tmp_path)
    reader = FixtureReader(fixture_root)

    # When: manager identity rows are derived from the fixture.
    managers, team_seasons = load_team_seasons(reader)
    summary = manager_summary(managers, team_seasons)
    rows = manager_rows(managers=managers, team_seasons=team_seasons)

    # Then: the unresolved fallback bucket is exact and excluded with caveats.
    assert "unresolved:2024:7" in managers
    assert summary.all_team_seasons_mapped is False
    unresolved = next(row for row in rows if row["managerKey"] == "unresolved:2024:7")
    assert unresolved["scoreEligible"] is False
    assert unresolved["aliases"] == [{"season": 2024, "teamId": 7, "teamName": "Team 7"}]
    assert unresolved["caveats"] == ["missing ESPN owner data; score excluded"]


def _team_season(
    *,
    team_id: int,
    manager_key: str,
    points_for: float,
) -> TeamSeason:
    return TeamSeason(
        season=2024,
        team_id=team_id,
        team_name=f"Team {team_id}",
        manager_key=manager_key,
        wins=team_id,
        losses=2 - team_id,
        ties=0,
        points_for=points_for,
        points_against=900.0,
        source_file="test",
    )


def _trade_summary() -> TradeAnalytics:
    return TradeAnalytics(
        completed_trade_accept_rows=10,
        graded_rows=8,
        ungraded_rows=2,
        canonical_graded_trade_events=8,
        canonical_groups_with_multiple_rows=0,
        item_sources={},
        ungraded_reasons={"missing_grade": 2},
    )


def _acquisition_summary() -> AcquisitionAnalytics:
    return AcquisitionAnalytics(
        total_rows=20,
        counted_rows=15,
        excluded_rows=5,
        type_counts={"WAIVER": 20},
        status_counts={"EXECUTED": 20},
        exclusion_reasons={"not_waiver_or_free_agent": 5},
        gross_rows=20,
        net_rows=15,
        faab_warning="FAAB context unavailable: bidAmount is always 0",
    )


def _write_minimal_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "fixture"
    season_dir = root / "season_2024"
    season_dir.mkdir(parents=True)
    _write_json(root / "export_manifest.json", {"seasons": [2024]})
    _write_json(
        season_dir / "_season_summary.json",
        {
            "final_scoring_period": 14,
            "transactions_total": 1,
            "schedule_items": 1,
        },
    )
    _write_json(
        season_dir / "core.json",
        {
            "data": {
                "members": [],
                "teams": [
                    {
                        "id": 7,
                        "record": {
                            "overall": {
                                "wins": 0,
                                "losses": 1,
                                "ties": 0,
                                "pointsFor": 90.0,
                                "pointsAgainst": 100.0,
                            }
                        },
                    }
                ],
            }
        },
    )
    return root


def _write_json(path: Path, payload: JsonValue) -> None:
    _ = path.write_text(json.dumps(payload), encoding="utf-8")
