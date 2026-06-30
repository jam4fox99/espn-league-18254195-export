from __future__ import annotations

from copy import deepcopy
from http import HTTPStatus
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from pydantic import ValidationError

from mygm_api import schemas
from mygm_api.models import VersionId
from tests.contracts.test_all_declared_endpoints import (
    create_authorized_league,
    store_credentials,
)

if TYPE_CHECKING:
    from tests.conftest import ApiHarness

type JsonValue = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)
type JsonObject = dict[str, JsonValue]

SNAPSHOT_VERSION = "espn-league-analytics-snapshot-v1"
MIN_MANAGER_COUNT = 2
SNAPSHOT_SEASON = 2025
TEAM_ONE_ID = 7
SNAPSHOT_VERSION_ID = VersionId(UUID("00000000-0000-0000-0000-000000000123"))


def test_api_schema_accepts_league_analytics_snapshot_contract() -> None:
    model = getattr(schemas, "LeagueAnalyticsSnapshotResponse", None)
    assert model is not None, "missing LeagueAnalyticsSnapshotResponse schema"

    snapshot = model.model_validate(_snapshot_payload())
    payload = snapshot.model_dump(by_alias=True)

    assert set(payload) == {
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
    assert payload["meta"]["snapshotVersion"] == SNAPSHOT_VERSION
    assert len(payload["managers"]) >= MIN_MANAGER_COUNT
    assert len(payload["trades"]["items"]) == 1
    assert len(payload["waivers"]["items"]) == 1
    assert len(payload["records"]["items"]) == 1
    assert len(payload["headToHead"]["pairs"]) == 1
    assert payload["dataHealth"]["caveats"]


def test_api_schema_rejects_snapshot_without_required_manager_key() -> None:
    model = getattr(schemas, "LeagueAnalyticsSnapshotResponse", None)
    assert model is not None, "missing LeagueAnalyticsSnapshotResponse schema"
    payload = deepcopy(_snapshot_payload())
    managers = payload["managers"]
    assert isinstance(managers, list)
    first_manager = managers[0]
    assert isinstance(first_manager, dict)
    _ = first_manager.pop("managerKey")

    with pytest.raises(ValidationError, match="managerKey"):
        model.model_validate(payload)


def test_private_analytics_routes_require_current_snapshot_when_authorized(
    api_harness: ApiHarness,
) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)

    response = api_harness.client.get(
        f"/v1/leagues/{league_id}/dashboard",
        headers=api_harness.headers,
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["detail"] == "analytics snapshot required"


def test_private_analytics_routes_serve_current_snapshot_rows_and_details(
    api_harness: ApiHarness,
) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)
    snapshot = _seed_snapshot(api_harness, league_id)
    manager_key = snapshot.managers[0].manager_key
    trade_id = snapshot.trades.items[0].trade_id
    waiver_id = snapshot.waivers.items[0].move_id
    pair = snapshot.head_to_head.pairs[0]

    dashboard = api_harness.client.get(
        f"/v1/leagues/{league_id}/dashboard",
        headers=api_harness.headers,
    )
    leaderboard = api_harness.client.get(
        f"/v1/leagues/{league_id}/leaderboard",
        headers=api_harness.headers,
    )
    manager = api_harness.client.get(
        f"/v1/leagues/{league_id}/gms/{manager_key}",
        headers=api_harness.headers,
    )
    trades = api_harness.client.get(f"/v1/leagues/{league_id}/trades", headers=api_harness.headers)
    trade_detail = api_harness.client.get(
        f"/v1/leagues/{league_id}/trades/{trade_id}",
        headers=api_harness.headers,
    )
    waiver_detail = api_harness.client.get(
        f"/v1/leagues/{league_id}/waivers/{waiver_id}",
        headers=api_harness.headers,
    )
    waivers = api_harness.client.get(
        f"/v1/leagues/{league_id}/waivers",
        headers=api_harness.headers,
    )
    head_to_head = api_harness.client.get(
        f"/v1/leagues/{league_id}/head-to-head",
        headers=api_harness.headers,
        params={
            "season": "all",
            "managerA": "espn-owner:owner-1",
            "managerB": "espn-owner:owner-2",
        },
    )
    season_head_to_head = api_harness.client.get(
        f"/v1/leagues/{league_id}/head-to-head",
        headers=api_harness.headers,
        params={
            "season": str(SNAPSHOT_SEASON),
            "managerA": pair.manager_a_key,
            "managerB": pair.manager_b_key,
        },
    )
    formula = api_harness.client.get(
        f"/v1/leagues/{league_id}/formula",
        headers=api_harness.headers,
    )
    data_health = api_harness.client.get(
        f"/v1/leagues/{league_id}/data-health",
        headers=api_harness.headers,
    )
    seasons = api_harness.client.get(
        f"/v1/leagues/{league_id}/seasons",
        headers=api_harness.headers,
    )

    assert dashboard.status_code == HTTPStatus.OK
    assert dashboard.json()["sourceCounts"]["canonicalTradeEvents"] == 1
    assert leaderboard.status_code == HTTPStatus.OK
    assert len(leaderboard.json()["rows"]) == 1
    assert manager.status_code == HTTPStatus.OK
    assert manager.json()["managerKey"] == manager_key
    assert manager.json()["teamAliases"][0]["teamId"] == TEAM_ONE_ID
    assert trades.status_code == HTTPStatus.OK
    assert len(trades.json()["rows"]) == 1
    assert trade_detail.status_code == HTTPStatus.OK
    assert trade_detail.json()["item"]["tradeId"] == trade_id
    assert waiver_detail.status_code == HTTPStatus.OK
    assert waiver_detail.json()["item"]["moveId"] == waiver_id
    assert waivers.status_code == HTTPStatus.OK
    assert len(waivers.json()["rows"]) == 1
    assert head_to_head.status_code == HTTPStatus.OK
    assert head_to_head.json()["pairs"][0]["pairId"] == "owner-1-owner-2"
    assert season_head_to_head.status_code == HTTPStatus.OK
    assert season_head_to_head.json()["pairs"][0]["matchups"][0]["season"] == SNAPSHOT_SEASON
    assert formula.status_code == HTTPStatus.OK
    assert formula.json()["formulaVersion"] == "mygm-retrospective-v1"
    assert data_health.status_code == HTTPStatus.OK
    assert data_health.json()["status"] == "caveated"
    assert seasons.status_code == HTTPStatus.OK
    assert seasons.json()["seasons"] == [SNAPSHOT_SEASON]


def test_reprocess_guard_rejects_duplicate_same_league_run_and_keeps_current_pointer(
    api_harness: ApiHarness,
) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)
    store_credentials(api_harness.client, api_harness.headers, league_id)
    _seed_snapshot(api_harness, league_id)
    import_run = api_harness.client.post(
        f"/v1/leagues/{league_id}/import-runs",
        headers=api_harness.headers,
        json={
            "startYear": 2020,
            "endYear": 2025,
            "includeActivity": True,
            "forceRefresh": False,
        },
    )
    payload = {
        "sourceImportRunId": import_run.json()["runId"],
        "targets": ["analyticsSnapshot"],
        "formulaVersion": "mygm-retrospective-v1",
    }

    first = api_harness.client.post(
        f"/v1/leagues/{league_id}/reprocess-runs",
        headers=api_harness.headers,
        json=payload,
    )
    second = api_harness.client.post(
        f"/v1/leagues/{league_id}/reprocess-runs",
        headers=api_harness.headers,
        json=payload,
    )
    status_response = api_harness.client.get(
        f"/v1/reprocess-runs/{first.json()['runId']}",
        headers=api_harness.headers,
    )
    dashboard = api_harness.client.get(
        f"/v1/leagues/{league_id}/dashboard",
        headers=api_harness.headers,
    )

    assert first.status_code == HTTPStatus.ACCEPTED
    assert first.json()["status"] == "queued"
    assert status_response.status_code == HTTPStatus.OK
    assert status_response.json()["status"] == "queued"
    assert status_response.json()["sourceCounts"]["canonicalTradeEvents"] == 1
    assert status_response.json()["caveats"] == ["FAAB context unavailable"]
    assert second.status_code == HTTPStatus.CONFLICT
    assert second.json()["detail"] == "analytics recompute already queued"
    assert dashboard.status_code == HTTPStatus.OK
    assert dashboard.json()["version"] == str(SNAPSHOT_VERSION_ID)


def test_reprocess_accepts_legacy_analytics_snapshot_target(
    api_harness: ApiHarness,
) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)
    store_credentials(api_harness.client, api_harness.headers, league_id)
    _seed_snapshot(api_harness, league_id)
    import_run = api_harness.client.post(
        f"/v1/leagues/{league_id}/import-runs",
        headers=api_harness.headers,
        json={
            "startYear": 2020,
            "endYear": 2025,
            "includeActivity": True,
            "forceRefresh": False,
        },
    )

    response = api_harness.client.post(
        f"/v1/leagues/{league_id}/reprocess-runs",
        headers=api_harness.headers,
        json={
            "sourceImportRunId": import_run.json()["runId"],
            "targets": ["analytics_snapshot"],
            "formulaVersion": "mygm-retrospective-v1",
        },
    )

    assert response.status_code == HTTPStatus.ACCEPTED
    assert response.json()["status"] == "queued"


def test_reprocess_rejects_unsupported_target_and_formula_version(
    api_harness: ApiHarness,
) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)
    store_credentials(api_harness.client, api_harness.headers, league_id)
    import_run = api_harness.client.post(
        f"/v1/leagues/{league_id}/import-runs",
        headers=api_harness.headers,
        json={
            "startYear": 2020,
            "endYear": 2025,
            "includeActivity": True,
            "forceRefresh": False,
        },
    )

    unsupported_target = api_harness.client.post(
        f"/v1/leagues/{league_id}/reprocess-runs",
        headers=api_harness.headers,
        json={
            "sourceImportRunId": import_run.json()["runId"],
            "targets": ["draftGrades"],
            "formulaVersion": "mygm-retrospective-v1",
        },
    )
    unsupported_formula = api_harness.client.post(
        f"/v1/leagues/{league_id}/reprocess-runs",
        headers=api_harness.headers,
        json={
            "sourceImportRunId": import_run.json()["runId"],
            "targets": ["analyticsSnapshot"],
            "formulaVersion": "experimental",
        },
    )

    assert unsupported_target.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert unsupported_target.json()["detail"] == "unsupported reprocess target"
    assert unsupported_formula.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert unsupported_formula.json()["detail"] == "unsupported formula version"


def test_reprocess_rejects_source_import_run_from_another_league(
    api_harness: ApiHarness,
) -> None:
    first_league_id = create_authorized_league(api_harness.client, api_harness.headers)
    store_credentials(api_harness.client, api_harness.headers, first_league_id)
    second_league = api_harness.client.post(
        "/v1/leagues",
        headers=api_harness.headers,
        json={"espnLeagueId": "18254196", "name": "Second League"},
    )
    second_league_id = second_league.json()["leagueId"]
    store_credentials(api_harness.client, api_harness.headers, second_league_id)
    import_run = api_harness.client.post(
        f"/v1/leagues/{first_league_id}/import-runs",
        headers=api_harness.headers,
        json={
            "startYear": 2020,
            "endYear": 2025,
            "includeActivity": True,
            "forceRefresh": False,
        },
    )

    response = api_harness.client.post(
        f"/v1/leagues/{second_league_id}/reprocess-runs",
        headers=api_harness.headers,
        json={
            "sourceImportRunId": import_run.json()["runId"],
            "targets": ["analytics_snapshot"],
            "formulaVersion": "mygm-retrospective-v1",
        },
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["detail"] == "source import run not found"


def test_public_share_payload_excludes_raw_owner_keys(api_harness: ApiHarness) -> None:
    response = api_harness.client.get("/v1/share/privacy-check")

    assert response.status_code == HTTPStatus.OK
    assert "espn-owner:" not in response.text
    assert "ownerId" not in response.text


def _snapshot_payload() -> JsonObject:
    return {
        "meta": {
            "snapshotVersion": SNAPSHOT_VERSION,
            "source": "espn",
            "generatedAt": "fixture-contract",
            "productLabel": "Retrospective GM Rating",
            "formulaVersion": "mygm-retrospective-v1",
            "importStatus": "available",
        },
        "league": {
            "leagueId": "fixture-league",
            "name": "Fixture League",
            "platform": "espn",
        },
        "seasons": [
            {"season": SNAPSHOT_SEASON, "finalWeek": 14, "isPartial": False},
        ],
        "managers": [
            {
                "managerKey": "espn-owner:owner-1",
                "aliases": [{"season": SNAPSHOT_SEASON, "teamId": TEAM_ONE_ID, "teamName": "One"}],
                "displayName": "Manager One",
                "ownerId": "owner-1",
                "scoreEligible": True,
                "caveats": [],
            },
            {
                "managerKey": "espn-owner:owner-2",
                "aliases": [{"season": SNAPSHOT_SEASON, "teamId": 9, "teamName": "Two"}],
                "displayName": "Manager Two",
                "ownerId": "owner-2",
                "scoreEligible": True,
                "caveats": [],
            },
        ],
        "leaderboards": {
            "allTime": [
                {
                    "rank": 1,
                    "managerKey": "espn-owner:owner-1",
                    "score": 87.5,
                    "confidence": "high",
                },
            ],
            "bySeason": [],
        },
        "trades": {
            "items": [
                {
                    "tradeId": "trade-1",
                    "season": SNAPSHOT_SEASON,
                    "managerKeys": ["espn-owner:owner-1", "espn-owner:owner-2"],
                    "scoreEligible": False,
                    "caveats": ["contract fixture trade row"],
                },
            ],
        },
        "waivers": {
            "items": [
                {
                    "moveId": "waiver-1",
                    "season": SNAPSHOT_SEASON,
                    "managerKey": "espn-owner:owner-1",
                    "transactionType": "WAIVER",
                    "scoreEligible": False,
                    "caveats": ["FAAB context unavailable"],
                },
            ],
        },
        "records": {
            "items": [
                {
                    "recordId": "highest-weekly-score",
                    "category": "weeklyScore",
                    "label": "Highest weekly score",
                    "value": 161.2,
                    "managerKey": "espn-owner:owner-1",
                },
            ],
        },
        "headToHead": {
            "pairs": [
                {
                    "pairId": "owner-1-owner-2",
                    "managerAKey": "espn-owner:owner-1",
                    "managerBKey": "espn-owner:owner-2",
                    "matchups": [
                        {
                            "season": SNAPSHOT_SEASON,
                            "week": 1,
                            "teamAScore": 100.0,
                            "teamBScore": 90.0,
                            "result": "A",
                            "isPlayoff": False,
                        },
                    ],
                    "caveats": ["contract fixture pair"],
                },
            ],
        },
        "dataHealth": {
            "status": "caveated",
            "sourceCounts": {"canonicalTradeEvents": 1},
            "careerExcludedSeasons": [2026],
            "caveats": ["FAAB context unavailable"],
            "warnings": ["partial season excluded"],
            "withheldScores": ["FAAB-adjusted waiver context"],
        },
        "formula": {
            "formulaVersion": "mygm-retrospective-v1",
            "provenance": "fixture-derived ESPN export analytics",
            "weights": {
                "tradePerformance": 0.35,
                "waiverPerformance": 0.35,
                "recordAndPoints": 0.2,
                "luckAdjusted": 0.1,
            },
        },
    }


def _seed_snapshot(
    api_harness: ApiHarness,
    league_id: str,
    *,
    extra_source_counts: dict[str, int] | None = None,
) -> schemas.LeagueAnalyticsSnapshotResponse:
    payload = deepcopy(_snapshot_payload())
    if extra_source_counts:
        data_health = payload["dataHealth"]
        assert isinstance(data_health, dict)
        source_counts = data_health["sourceCounts"]
        assert isinstance(source_counts, dict)
        source_counts.update(extra_source_counts)
    snapshot = schemas.LeagueAnalyticsSnapshotResponse.model_validate(payload)
    parsed_league_id = next(
        store_league_id
        for store_league_id in api_harness.store.leagues
        if str(store_league_id) == league_id
    )
    api_harness.store.analytics_snapshots[(parsed_league_id, SNAPSHOT_VERSION_ID)] = snapshot
    api_harness.store.current_analytics_version_by_league[parsed_league_id] = SNAPSHOT_VERSION_ID
    return snapshot


def test_leaderboard_defaults_to_v2_and_supports_v1_formula_toggle(
    api_harness: ApiHarness,
) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)
    _seed_dual_formula_snapshot(api_harness, league_id)

    default_leaderboard = api_harness.client.get(
        f"/v1/leagues/{league_id}/leaderboard",
        headers=api_harness.headers,
    )
    v1_leaderboard = api_harness.client.get(
        f"/v1/leagues/{league_id}/leaderboard",
        headers=api_harness.headers,
        params={"formula": "mygm-retrospective-v1"},
    )
    formula = api_harness.client.get(
        f"/v1/leagues/{league_id}/formula",
        headers=api_harness.headers,
    )

    assert default_leaderboard.status_code == HTTPStatus.OK
    default_row = default_leaderboard.json()["rows"][0]
    assert default_row["score"] == 65.0
    assert "tradeValue" in default_row["componentBreakdown"]
    assert "luckAdjusted" not in default_row["componentBreakdown"]

    assert v1_leaderboard.status_code == HTTPStatus.OK
    v1_row = v1_leaderboard.json()["rows"][0]
    assert v1_row["score"] == 87.5
    assert "tradePerformance" in v1_row["componentBreakdown"]

    assert formula.status_code == HTTPStatus.OK
    body = formula.json()
    assert body["formulaVersion"] == "mygm-historian-v2"
    available = {item["formulaVersion"] for item in body["availableFormulas"]}
    assert available == {"mygm-historian-v2", "mygm-retrospective-v1"}


def test_history_endpoint_returns_descending_timeline_with_champions(
    api_harness: ApiHarness,
) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)
    payload = deepcopy(_snapshot_payload())
    payload["seasons"] = [
        {
            "season": 2024,
            "finalWeek": 14,
            "isPartial": False,
            "transactionCount": 42,
            "champion": {
                "managerKey": "espn-owner:owner-1",
                "displayName": "Manager One",
                "teamName": "One",
            },
            "runnerUp": {"managerKey": "espn-owner:owner-2", "displayName": "Manager Two"},
            "superlatives": [{"label": "Draft steal", "displayName": "Manager One", "value": 99.0}],
        },
        {"season": 2025, "finalWeek": 3, "isPartial": True},
    ]
    snapshot = schemas.LeagueAnalyticsSnapshotResponse.model_validate(payload)
    parsed_league_id = next(
        store_league_id
        for store_league_id in api_harness.store.leagues
        if str(store_league_id) == league_id
    )
    api_harness.store.analytics_snapshots[(parsed_league_id, SNAPSHOT_VERSION_ID)] = snapshot
    api_harness.store.current_analytics_version_by_league[parsed_league_id] = SNAPSHOT_VERSION_ID

    response = api_harness.client.get(
        f"/v1/leagues/{league_id}/history",
        headers=api_harness.headers,
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["span"] == "2024\u20132025"
    assert body["seasonCount"] == 2
    # Seasons are returned newest-first.
    assert [season["season"] for season in body["seasons"]] == [2025, 2024]
    partial, completed = body["seasons"]
    assert partial["isPartial"] is True
    assert "in progress" in partial["headline"].lower()
    assert completed["champion"]["displayName"] == "Manager One"
    assert "won the championship" in completed["headline"]
    assert len(completed["superlatives"]) == 1
    assert body["champions"] == [
        {"managerKey": "espn-owner:owner-1", "displayName": "Manager One", "titles": 1},
    ]


def test_manager_hub_aggregates_career_value_and_rivalry(api_harness: ApiHarness) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)
    payload = deepcopy(_snapshot_payload())
    managers = payload["managers"]
    assert isinstance(managers, list)
    first = managers[0]
    assert isinstance(first, dict)
    first["career"] = {
        "seasonsPlayed": 5,
        "wins": 40,
        "losses": 30,
        "winPct": 57.1,
        "titles": 2,
        "bestFinish": 1,
        "eras": [{"kind": "dynasty", "startSeason": 2022, "endSeason": 2023, "titles": 2}],
        "seasonLines": [{"season": 2024, "rankFinal": 1, "ratingScore": 88.0, "teamName": "One"}],
    }
    first["value"] = {
        "trade": {"netPoints": 120.0, "tradeCount": 8, "partners": []},
        "waiver": {"netPoints": 300.0, "bestPickup": {"summary": "2024: added a WR1"}},
    }
    first["rivalry"] = {
        "nemesis": {"opponentDisplayName": "Manager Two", "winPct": 25.0, "games": 4},
        "favorite": {"opponentDisplayName": "Manager Two", "winPct": 75.0, "games": 4},
        "edges": [],
    }
    leaderboards = payload["leaderboards"]
    assert isinstance(leaderboards, dict)
    leaderboards["allTime"] = [
        {
            "rank": 1,
            "managerKey": "espn-owner:owner-1",
            "score": 84.0,
            "confidence": "high",
            "components": {
                "tradeValue": 80.0,
                "waiverValue": 90.0,
                "lineupEfficiency": 70.0,
                "recordAndPoints": 85.0,
            },
        },
    ]
    snapshot = schemas.LeagueAnalyticsSnapshotResponse.model_validate(payload)
    parsed_league_id = next(
        store_league_id
        for store_league_id in api_harness.store.leagues
        if str(store_league_id) == league_id
    )
    api_harness.store.analytics_snapshots[(parsed_league_id, SNAPSHOT_VERSION_ID)] = snapshot
    api_harness.store.current_analytics_version_by_league[parsed_league_id] = SNAPSHOT_VERSION_ID

    directory = api_harness.client.get(
        f"/v1/leagues/{league_id}/managers",
        headers=api_harness.headers,
    )
    hub = api_harness.client.get(
        f"/v1/leagues/{league_id}/managers/espn-owner:owner-1",
        headers=api_harness.headers,
    )
    missing = api_harness.client.get(
        f"/v1/leagues/{league_id}/managers/espn-owner:ghost",
        headers=api_harness.headers,
    )

    assert directory.status_code == HTTPStatus.OK
    top = directory.json()["managers"][0]
    assert top["managerKey"] == "espn-owner:owner-1"
    assert top["careerRating"] == 84.0
    assert top["titles"] == 2

    assert hub.status_code == HTTPStatus.OK
    body = hub.json()
    assert body["careerRating"] == 84.0
    assert set(body["ratingComponents"]) == {
        "tradeValue",
        "waiverValue",
        "lineupEfficiency",
        "recordAndPoints",
    }
    assert body["career"]["titles"] == 2
    assert body["career"]["eras"][0]["kind"] == "dynasty"
    assert body["value"]["trade"]["tradeCount"] == 8
    assert body["rivalry"]["nemesis"]["opponentDisplayName"] == "Manager Two"

    assert missing.status_code == HTTPStatus.NOT_FOUND


def test_rivalries_endpoint_returns_matrix_managers_edges_and_summaries(
    api_harness: ApiHarness,
) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)
    payload = deepcopy(_snapshot_payload())
    payload["rivalries"] = {
        "managers": [
            {"managerKey": "espn-owner:owner-1", "displayName": "Manager One"},
            {"managerKey": "espn-owner:owner-2", "displayName": "Manager Two"},
        ],
        "edges": [
            {
                "managerKey": "espn-owner:owner-1",
                "opponentKey": "espn-owner:owner-2",
                "opponentDisplayName": "Manager Two",
                "games": 4,
                "wins": 3,
                "losses": 1,
                "winPct": 75.0,
            },
        ],
        "summaries": [
            {
                "managerKey": "espn-owner:owner-1",
                "displayName": "Manager One",
                "favorite": {"opponentDisplayName": "Manager Two", "winPct": 75.0},
                "nemesis": {"opponentDisplayName": "Manager Two", "winPct": 75.0},
            },
        ],
    }
    snapshot = schemas.LeagueAnalyticsSnapshotResponse.model_validate(payload)
    parsed_league_id = next(
        store_league_id
        for store_league_id in api_harness.store.leagues
        if str(store_league_id) == league_id
    )
    api_harness.store.analytics_snapshots[(parsed_league_id, SNAPSHOT_VERSION_ID)] = snapshot
    api_harness.store.current_analytics_version_by_league[parsed_league_id] = SNAPSHOT_VERSION_ID

    response = api_harness.client.get(
        f"/v1/leagues/{league_id}/rivalries",
        headers=api_harness.headers,
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert len(body["managers"]) == 2
    assert len(body["edges"]) == 1
    assert body["edges"][0]["winPct"] == 75.0
    assert body["summaries"][0]["nemesis"]["opponentDisplayName"] == "Manager Two"


def test_player_leaderboards_returns_top_weeks_seasons_and_efficiency(
    api_harness: ApiHarness,
) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)
    payload = deepcopy(_snapshot_payload())
    payload["playerLeaderboards"] = {
        "topWeeks": [
            {
                "playerName": "Star Player",
                "position": "RB",
                "season": 2023,
                "week": 5,
                "points": 51.2,
                "managerKey": "espn-owner:owner-1",
                "displayName": "Manager One",
                "teamName": "Team One",
            },
        ],
        "topSeasons": [
            {
                "playerName": "Star Player",
                "position": "RB",
                "season": 2023,
                "points": 320.5,
                "weeks": 16,
                "managerKey": "espn-owner:owner-1",
                "displayName": "Manager One",
                "teamName": "Team One",
            },
        ],
    }
    payload["lineupEfficiency"] = {
        "seasons": [
            {
                "season": 2023,
                "managerKey": "espn-owner:owner-1",
                "displayName": "Manager One",
                "teamName": "Team One",
                "aggregateEfficiency": 92.5,
                "avgEfficiency": 91.0,
                "benchPoints": 180.0,
                "startedPoints": 1700.0,
                "optimalPoints": 1840.0,
                "weeksCounted": 16,
            },
        ],
    }
    snapshot = schemas.LeagueAnalyticsSnapshotResponse.model_validate(payload)
    parsed_league_id = next(
        store_league_id
        for store_league_id in api_harness.store.leagues
        if str(store_league_id) == league_id
    )
    api_harness.store.analytics_snapshots[(parsed_league_id, SNAPSHOT_VERSION_ID)] = snapshot
    api_harness.store.current_analytics_version_by_league[parsed_league_id] = SNAPSHOT_VERSION_ID

    response = api_harness.client.get(
        f"/v1/leagues/{league_id}/players/leaderboards",
        headers=api_harness.headers,
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert len(body["topWeeks"]) == 1
    assert body["topWeeks"][0]["playerName"] == "Star Player"
    assert body["topSeasons"][0]["points"] == 320.5
    assert len(body["lineupEfficiency"]) == 1
    assert body["lineupEfficiency"][0]["aggregateEfficiency"] == 92.5


def test_season_hub_returns_standings_champion_and_review(api_harness: ApiHarness) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)
    payload = deepcopy(_snapshot_payload())
    payload["seasons"] = [
        {
            "season": 2024,
            "finalWeek": 14,
            "isPartial": False,
            "transactionCount": 120,
            "playoffTeamCount": 6,
            "champion": {
                "managerKey": "espn-owner:owner-1",
                "displayName": "Manager One",
                "teamName": "One",
            },
            "runnerUp": {"managerKey": "espn-owner:owner-2", "displayName": "Manager Two"},
            "finalStandings": [
                {
                    "managerKey": "espn-owner:owner-1",
                    "displayName": "Manager One",
                    "rankFinal": 1,
                    "wins": 11,
                    "losses": 3,
                    "pointsFor": 1800.0,
                    "isChampion": True,
                },
                {
                    "managerKey": "espn-owner:owner-2",
                    "displayName": "Manager Two",
                    "rankFinal": 2,
                    "wins": 9,
                    "losses": 5,
                    "pointsFor": 1700.0,
                    "isChampion": False,
                },
            ],
            "draftRecap": {
                "pickCount": 2,
                "bestSteal": {
                    "displayName": "Manager One",
                    "playerName": "Late Round Hero",
                    "overallPick": 140,
                },
                "biggestBust": {
                    "displayName": "Manager Two",
                    "playerName": "First Round Flop",
                    "overallPick": 3,
                },
            },
            "superlatives": [{"label": "Draft steal", "displayName": "Manager One"}],
        },
    ]
    leaderboards = payload["leaderboards"]
    assert isinstance(leaderboards, dict)
    leaderboards["bySeason"] = [
        {
            "rank": 1,
            "managerKey": "espn-owner:owner-1",
            "season": 2024,
            "score": 82.0,
            "confidence": "high",
        },
    ]
    snapshot = schemas.LeagueAnalyticsSnapshotResponse.model_validate(payload)
    parsed_league_id = next(
        store_league_id
        for store_league_id in api_harness.store.leagues
        if str(store_league_id) == league_id
    )
    api_harness.store.analytics_snapshots[(parsed_league_id, SNAPSHOT_VERSION_ID)] = snapshot
    api_harness.store.current_analytics_version_by_league[parsed_league_id] = SNAPSHOT_VERSION_ID

    response = api_harness.client.get(
        f"/v1/leagues/{league_id}/seasons/2024/hub",
        headers=api_harness.headers,
    )
    missing = api_harness.client.get(
        f"/v1/leagues/{league_id}/seasons/1999/hub",
        headers=api_harness.headers,
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["champion"]["displayName"] == "Manager One"
    assert body["runnerUp"]["displayName"] == "Manager Two"
    assert len(body["finalStandings"]) == 2
    assert len(body["ratings"]) == 1
    assert body["ratings"][0]["managerName"] == "Manager One"
    assert body["draftRecap"]["bestSteal"]["playerName"] == "Late Round Hero"
    review = " ".join(body["review"])
    assert "Manager One won the championship with One (11-3)." in body["review"]
    assert "Late Round Hero" in review
    assert "120 roster moves" in review

    assert missing.status_code == HTTPStatus.NOT_FOUND


def _seed_dual_formula_snapshot(api_harness: ApiHarness, league_id: str) -> None:
    payload = deepcopy(_snapshot_payload())
    payload["meta"]["formulaVersion"] = "mygm-historian-v2"
    v2_leaderboards = {
        "allTime": [
            {
                "rank": 1,
                "managerKey": "espn-owner:owner-1",
                "score": 65.0,
                "confidence": "medium",
                "components": {
                    "tradeValue": 60.0,
                    "waiverValue": 70.0,
                    "lineupEfficiency": 55.0,
                    "recordAndPoints": 68.0,
                },
            },
        ],
        "bySeason": [],
    }
    v1_leaderboards = {
        "allTime": [
            {
                "rank": 1,
                "managerKey": "espn-owner:owner-1",
                "score": 87.5,
                "confidence": "high",
                "components": {
                    "tradePerformance": 80.0,
                    "waiverPerformance": 90.0,
                    "recordAndPoints": 85.0,
                    "luckAdjusted": 95.0,
                },
            },
        ],
        "bySeason": [],
    }
    payload["leaderboards"] = v2_leaderboards
    payload["formula"] = {
        "formulaVersion": "mygm-historian-v2",
        "provenance": "fixture-derived ESPN export analytics",
        "weights": {
            "tradeValue": 0.25,
            "waiverValue": 0.25,
            "lineupEfficiency": 0.15,
            "recordAndPoints": 0.35,
        },
        "componentLabels": {"tradeValue": "Trade value"},
    }
    payload["formulas"] = {
        "default": "mygm-historian-v2",
        "available": [
            {"formulaVersion": "mygm-historian-v2", "leaderboards": v2_leaderboards},
            {
                "formulaVersion": "mygm-retrospective-v1",
                "deprecated": True,
                "leaderboards": v1_leaderboards,
            },
        ],
    }
    snapshot = schemas.LeagueAnalyticsSnapshotResponse.model_validate(payload)
    parsed_league_id = next(
        store_league_id
        for store_league_id in api_harness.store.leagues
        if str(store_league_id) == league_id
    )
    api_harness.store.analytics_snapshots[(parsed_league_id, SNAPSHOT_VERSION_ID)] = snapshot
    api_harness.store.current_analytics_version_by_league[parsed_league_id] = SNAPSHOT_VERSION_ID


def test_data_health_surfaces_source_backed_ungraded_executed_accepts(
    api_harness: ApiHarness,
) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)
    _seed_snapshot(
        api_harness,
        league_id,
        extra_source_counts={"executedAcceptedTrades": 95, "gradedTradeRows": 70},
    )

    response = api_harness.client.get(
        f"/v1/leagues/{league_id}/data-health",
        headers=api_harness.headers,
    )

    assert response.status_code == HTTPStatus.OK
    # 95 executed accepts minus 70 graded rows = 25, derived from the snapshot's
    # own source counts rather than a hard-coded fixture fact.
    assert response.json()["ungradedExecutedAccepts"] == 25


def test_data_health_omits_ungraded_count_when_snapshot_lacks_inputs(
    api_harness: ApiHarness,
) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)
    _seed_snapshot(api_harness, league_id)

    response = api_harness.client.get(
        f"/v1/leagues/{league_id}/data-health",
        headers=api_harness.headers,
    )

    assert response.status_code == HTTPStatus.OK
    # No fabricated fallback: the field stays null when the snapshot cannot back it.
    assert response.json()["ungradedExecutedAccepts"] is None
