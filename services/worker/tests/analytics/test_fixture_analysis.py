from __future__ import annotations

from pathlib import Path

import pytest

from mygm_worker.analytics import (
    analyze_fixture,
    write_summary,
)
from mygm_worker.analytics import (
    payload as analytics_payload,
)
from mygm_worker.analytics.json_tools import as_array, as_object, int_value, string_value
from mygm_worker.analytics.payload import (
    dashboard_payload,
    write_analytics_snapshot,
    write_dashboard_payload,
)
from mygm_worker.analytics.report import PartialSeasonIncludedError

FIXTURE_ROOT = Path(__file__).parents[4] / "espn_exports" / "league_18254195"


def test_analyze_fixture_reports_required_counts() -> None:
    summary = analyze_fixture(FIXTURE_ROOT)

    assert summary.status == "PASS"
    # Trades reconstructed from box-score roster movement (every executed trade, all graded).
    assert summary.trade_analytics.completed_trade_accept_rows == 145
    assert summary.trade_analytics.graded_rows == 145
    assert summary.trade_analytics.ungraded_rows == 0
    assert summary.trade_analytics.canonical_graded_trade_events == 145
    assert summary.acquisition_analytics.type_counts["WAIVER"] == 2662
    assert summary.acquisition_analytics.type_counts["FREEAGENT"] == 1237
    assert summary.manager_identity.all_team_seasons_mapped
    assert summary.career_excluded_seasons == (2026,)


def test_every_acquisition_row_is_counted_or_excluded() -> None:
    summary = analyze_fixture(FIXTURE_ROOT)
    acquisitions = summary.acquisition_analytics

    expected_rows = acquisitions.type_counts["WAIVER"] + acquisitions.type_counts["FREEAGENT"]
    assert acquisitions.total_rows == expected_rows
    assert acquisitions.counted_rows + acquisitions.excluded_rows == expected_rows
    assert acquisitions.exclusion_reasons
    assert acquisitions.faab_warning == "FAAB context unavailable: bidAmount is always 0"


def test_gm_ratings_include_components_confidence_and_warnings() -> None:
    summary = analyze_fixture(FIXTURE_ROOT)

    assert summary.gm_ratings
    for rating in summary.gm_ratings:
        assert rating.formula_version == "mygm-retrospective-v1"
        assert set(rating.raw_components) == {
            "tradePerformance",
            "waiverPerformance",
            "recordAndPoints",
            "luckAdjusted",
        }
        assert set(rating.normalized_components) == set(rating.raw_components)
        assert set(rating.weights) == set(rating.raw_components)
        assert 0 <= rating.final_score <= 100
        assert rating.confidence in {"high", "medium", "low", "no_grade"}
        assert rating.warnings


def test_strict_mode_rejects_partial_career_season() -> None:
    with pytest.raises(PartialSeasonIncludedError, match="partial season cannot be included"):
        _ = analyze_fixture(FIXTURE_ROOT, include_partial_career=True, strict=True)


def test_write_summary_persists_fixture_summary(tmp_path: Path) -> None:
    output_dir = tmp_path / "analytics"
    written = write_summary(FIXTURE_ROOT, output_dir)

    assert written == output_dir / "summary.json"
    assert written.exists()
    assert '"status": "PASS"' in written.read_text(encoding="utf-8")


def test_dashboard_payload_exposes_api_ui_contract(tmp_path: Path) -> None:
    summary = analyze_fixture(FIXTURE_ROOT)
    payload = dashboard_payload(summary)

    dashboard = as_object(payload["dashboard"], "dashboard")
    trades = as_object(payload["trades"], "trades")
    waivers = as_object(payload["waivers"], "waivers")
    formula = as_object(payload["formula"], "formula")
    data_health = as_object(payload["data_health"], "data_health")
    visible_strings = [
        string_value(value)
        for value in as_array(payload["visible_strings"], "visible_strings")
    ]

    assert payload["payload_version"] == "mygm-fixture-dashboard-v1"
    assert dashboard["title"] == "Retrospective GM Rating"
    assert trades["canonical_graded_trade_events"] == 145
    assert trades["ungraded_executed_accepts"] == 0
    assert waivers["faab_context"] == "FAAB context unavailable: bidAmount is always 0"
    assert formula["version"] == "mygm-retrospective-v1"
    assert data_health["career_exclusion"] == "2026 excluded from career ratings"
    assert int_value(payload["gm_leaderboard_count"]) > 0
    assert "Retrospective GM Rating" in visible_strings
    assert "145 canonical graded trade events" in visible_strings
    assert "0 ungraded executed accepts" in visible_strings
    assert "FAAB context unavailable" in visible_strings
    assert "2026 excluded from career ratings" in visible_strings

    written = write_dashboard_payload(FIXTURE_ROOT, tmp_path)
    assert written == tmp_path / "dashboard_payload.json"
    assert '"payload_version": "mygm-fixture-dashboard-v1"' in written.read_text(
        encoding="utf-8"
    )


def test_league_analytics_snapshot_contract_accepts_fixture_sections() -> None:
    summary = analyze_fixture(FIXTURE_ROOT)
    payload = analytics_payload.league_analytics_snapshot(summary)

    expected_sections = {
        "meta",
        "league",
        "seasons",
        "managers",
        "leaderboards",
        "trades",
        "waivers",
        "records",
        "headToHead",
        "dataHealth",
        "formula",
    }
    assert expected_sections <= set(payload)

    snapshot = analytics_payload.read_league_analytics_snapshot(payload)
    meta = as_object(snapshot["meta"], "meta")
    managers = as_array(snapshot["managers"], "managers")
    trades = as_object(snapshot["trades"], "trades")
    waivers = as_object(snapshot["waivers"], "waivers")
    records = as_object(snapshot["records"], "records")
    head_to_head = as_object(snapshot["headToHead"], "headToHead")
    data_health = as_object(snapshot["dataHealth"], "dataHealth")

    assert meta["snapshotVersion"] == "espn-league-analytics-snapshot-v1"
    assert len(managers) >= 2
    assert len(as_array(trades["items"], "trades.items")) >= 1
    assert len(as_array(waivers["items"], "waivers.items")) >= 1
    assert len(as_array(records["items"], "records.items")) >= 1
    assert len(as_array(head_to_head["pairs"], "headToHead.pairs")) >= 1
    assert as_array(data_health["caveats"], "dataHealth.caveats")


def test_league_analytics_snapshot_uses_derived_fixture_rows(tmp_path: Path) -> None:
    summary = analyze_fixture(FIXTURE_ROOT)
    payload = analytics_payload.league_analytics_snapshot(
        summary,
        FIXTURE_ROOT,
        league_id="18254195",
    )

    league = as_object(payload["league"], "league")
    managers = as_array(payload["managers"], "managers")
    leaderboards = as_object(payload["leaderboards"], "leaderboards")
    trades = as_object(payload["trades"], "trades")
    waivers = as_object(payload["waivers"], "waivers")
    records = as_object(payload["records"], "records")
    head_to_head = as_object(payload["headToHead"], "headToHead")
    data_health = as_object(payload["dataHealth"], "dataHealth")
    formula = as_object(payload["formula"], "formula")

    trade_items = as_array(trades["items"], "trades.items")
    waiver_items = as_array(waivers["items"], "waivers.items")
    record_items = as_array(records["items"], "records.items")
    pairs = as_array(head_to_head["pairs"], "headToHead.pairs")

    assert league["leagueId"] == "18254195"
    assert any(
        string_value(as_object(manager, "manager")["managerKey"]).startswith("espn-owner:")
        for manager in managers
    )
    assert as_array(leaderboards["allTime"], "leaderboards.allTime")
    assert as_array(leaderboards["bySeason"], "leaderboards.bySeason")
    assert len(trade_items) >= summary.trade_analytics.completed_trade_accept_rows
    assert len(waiver_items) == summary.acquisition_analytics.total_rows
    assert {string_value(as_object(record, "record")["category"]) for record in record_items} >= {
        "highest_weekly_score",
        "lowest_weekly_score",
        "closest_matchup",
        "largest_matchup",
        "best_season_record",
        "worst_season_record",
        "most_season_points",
    }
    assert pairs
    assert as_array(as_object(pairs[0], "headToHead.pairs[0]")["matchups"], "matchups")
    assert as_array(data_health["caveats"], "dataHealth.caveats")
    # v3 (mygm-historian-v3) is the default formula: trade/waiver/draft use VOR, plus luck.
    assert formula["formulaVersion"] == "mygm-historian-v3"
    assert formula["weights"] == {
        "tradeValue": 0.2,
        "waiverValue": 0.2,
        "lineupEfficiency": 0.15,
        "recordAndPoints": 0.2,
        "draftValue": 0.15,
        "luck": 0.1,
    }
    assert "luckAdjusted" not in as_object(formula["weights"], "formula.weights")
    # v2 and v1 remain available for the toggle.
    formulas = as_object(payload["formulas"], "formulas")
    available = {
        string_value(as_object(item, "formula")["formulaVersion"])
        for item in as_array(formulas["available"], "formulas.available")
    }
    assert available == {"mygm-historian-v3", "mygm-historian-v2", "mygm-retrospective-v1"}

    written = write_analytics_snapshot(
        FIXTURE_ROOT,
        tmp_path,
        league_id="18254195",
        summary=summary,
    )
    assert written == tmp_path / "analytics_snapshot.json"
    text = written.read_text(encoding="utf-8")
    assert '"snapshotVersion": "espn-league-analytics-snapshot-v1"' in text
    assert "espn_s2" not in text
    assert "SWID" not in text


def test_snapshot_exposes_roster_history_and_waiver_superlatives() -> None:
    summary = analyze_fixture(FIXTURE_ROOT)
    payload = analytics_payload.league_analytics_snapshot(
        summary,
        FIXTURE_ROOT,
        league_id="18254195",
    )

    # Roster history rides on each manager row (like draftCard) and as a top-level map.
    roster_history = as_object(payload["rosterHistory"], "rosterHistory")
    assert roster_history
    managers = as_array(payload["managers"], "managers")
    enriched = [
        manager
        for manager in managers
        if as_object(manager, "manager").get("rosterHistory") is not None
    ]
    assert enriched
    first = as_object(enriched[0], "manager")
    history = as_object(first["rosterHistory"], "rosterHistory")
    assert as_array(history["allTimeLineup"], "allTimeLineup")
    assert as_object(history["depthChart"], "depthChart")
    assert as_array(history["seasonRosters"], "seasonRosters")

    # Waiver superlatives are keyed by season string, surfaced top-level and on the section.
    superlatives = as_object(payload["waiverSuperlatives"], "waiverSuperlatives")
    assert "2025" in superlatives
    waivers = as_object(payload["waivers"], "waivers")
    section = as_object(waivers["superlatives"], "waivers.superlatives")
    assert "2025" in section
    cards = as_object(section["2025"], "superlatives[2025]")
    for card_key in ("bestPickup", "worstDrop", "bestWireValue", "mostActive"):
        card = as_object(cards[card_key], card_key)
        assert string_value(card["managerKey"])


def test_legacy_dashboard_payload_adapts_to_snapshot_with_deprecation_caveat() -> None:
    summary = analyze_fixture(FIXTURE_ROOT)
    legacy_payload = dashboard_payload(summary)

    snapshot = analytics_payload.read_league_analytics_snapshot(legacy_payload)
    data_health = as_object(snapshot["dataHealth"], "dataHealth")

    assert data_health["status"] == "caveated"
    assert "legacy fixture dashboard payload adapted" in as_array(
        data_health["caveats"],
        "dataHealth.caveats",
    )


def test_snapshot_validation_rejects_missing_required_manager_key() -> None:
    summary = analyze_fixture(FIXTURE_ROOT)
    payload = dashboard_payload(summary)
    snapshot = analytics_payload.read_league_analytics_snapshot(payload)
    managers = as_array(snapshot["managers"], "managers")
    first_manager = as_object(managers[0], "managers[0]")
    _ = first_manager.pop("managerKey")

    with pytest.raises(
        analytics_payload.SnapshotValidationError,
        match="managerKey",
    ):
        _ = analytics_payload.read_league_analytics_snapshot(snapshot)
