from __future__ import annotations

# pyright: reportAny=false, reportExplicitAny=false, reportUnknownVariableType=false
from pathlib import Path
from typing import Any

from mygm_worker.espn.import_jobs import (
    EspnImportRequest,
    ImportRunId,
    ImportStorageRequest,
    LeagueId,
    OrgId,
    TransformVersion,
    import_storage_paths,
    summarize_export,
)
from mygm_worker.espn.player_lookup import build_trade_coverage, read_json
from mygm_worker.espn.trade_grades import build_trade_grade_rows
from mygm_worker.fixtures import fixture_roots


def player_lookup_rows(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        message = "Expected player lookup dict"
        raise TypeError(message)
    rows: dict[str, dict[str, Any]] = {}
    for key, row in value.items():
        if not isinstance(key, str) or not isinstance(row, dict):
            message = "Expected player lookup rows keyed by player id"
            raise TypeError(message)
        rows[key] = row
    return rows


def test_export_summary_counts_when_fixture_manifest_is_loaded() -> None:
    roots = fixture_roots(Path(__file__))

    summary = summarize_export(
        EspnImportRequest(
            league_id=LeagueId("18254195"),
            export_root=roots.espn_export,
        )
    )

    assert summary.league_id == "18254195"
    assert summary.start_year == 2020
    assert summary.end_year == 2026
    assert len(summary.seasons) == 7
    assert sum(season.box_score_player_entries for season in summary.seasons) == 18333
    assert sum(season.transactions_total for season in summary.seasons) == 13144
    assert summary.players_total == 574
    assert summary.weekly_point_rows == 28294
    # Trades are reconstructed from box-score roster movement (see trade_reconstruct), which
    # recovers every executed trade across all seasons rather than the small, season-skewed
    # subset ESPN's unreliable transaction status exposed.
    assert summary.completed_trade_accept_rows == 145
    assert summary.graded_trade_rows == 145
    assert summary.canonical_graded_trade_groups == 145


def test_trade_grades_when_built_from_fixtures_reconstruct_all_executed_trades() -> None:
    roots = fixture_roots(Path(__file__))

    rows, summary = build_trade_grade_rows(
        export_root=roots.espn_export,
        include_trade_week=False,
    )

    # Every reconstructed trade is gradeable: it has both sides' players and post-trade points.
    assert len(rows) == 145
    assert summary["completed_trade_accept_rows"] == 145
    assert summary["graded_rows"] == 145
    assert summary["ungraded_rows"] == 0
    assert summary["canonical_graded_trade_groups"] == 145
    assert summary["trade_item_sources"] == {"roster_movement": 145}
    assert summary["ungraded_reasons"] == {}


def test_trade_coverage_when_lookup_fixture_is_loaded_has_no_missing_executed_points() -> None:
    roots = fixture_roots(Path(__file__))
    lookup = read_json(roots.espn_export / "player_lookup" / "player_weekly_points.json")

    players = player_lookup_rows(lookup["players"])
    coverage = build_trade_coverage(players)

    assert coverage == {
        "trade_player_ids": 415,
        "trade_player_ids_with_names": 415,
        "trade_player_ids_with_weekly_points": 415,
        "unresolved_name_player_ids": [],
        "no_weekly_points_player_ids": [],
        "executed_trade_accept_player_ids": 103,
        "executed_trade_accept_player_ids_without_points": [],
    }


def test_import_storage_paths_when_request_is_built_match_schema_contract() -> None:
    paths = import_storage_paths(
        ImportStorageRequest(
            org_id=OrgId("org_123"),
            league_id=LeagueId("18254195"),
            import_run_id=ImportRunId("run_456"),
            transform_version=TransformVersion("retrospective-v1"),
        )
    )

    assert paths.raw_import_prefix == "org/org_123/league/18254195/import/run_456/"
    assert (
        paths.derived_artifact_prefix
        == "league/18254195/source_import/run_456/transform/retrospective-v1/"
    )
