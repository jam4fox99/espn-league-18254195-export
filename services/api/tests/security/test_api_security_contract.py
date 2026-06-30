from http import HTTPStatus

from tests.conftest import ApiHarness
from tests.contracts.test_all_declared_endpoints import (
    create_authorized_league,
    store_credentials,
)

CANONICAL_TRADE_EVENTS = 51


def test_cors_preflight_allows_configured_local_web_origin(api_harness: ApiHarness) -> None:
    response = api_harness.client.options(
        "/v1/alpha-invites/accept",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )
    assert response.status_code == HTTPStatus.OK
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


def test_rate_limit_rejects_excessive_sensitive_write_attempts(
    api_harness: ApiHarness,
) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)
    body = {
        "leagueId": league_id,
        "SWID": "{TEST-SWID}",
        "espn_s2": "test-token",
        "consentVersion": "alpha-consent-v1",
        "startYear": 2020,
        "endYear": 2025,
    }
    for _ in range(20):
        response = api_harness.client.post(
            f"/v1/leagues/{league_id}/credentials",
            headers=api_harness.headers,
            json=body,
        )
        assert response.status_code == HTTPStatus.OK
    limited = api_harness.client.post(
        f"/v1/leagues/{league_id}/credentials",
        headers=api_harness.headers,
        json=body,
    )
    assert limited.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert "{TEST-SWID}" not in limited.text
    assert "test-token" not in limited.text


def test_artifact_manifest_route_denies_unauthenticated_access(
    api_harness: ApiHarness,
) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)
    store_credentials(api_harness.client, api_harness.headers, league_id)
    created = api_harness.client.post(
        f"/v1/leagues/{league_id}/import-runs",
        headers=api_harness.headers,
        json={
            "startYear": 2020,
            "endYear": 2025,
            "includeActivity": True,
            "forceRefresh": False,
        },
    )
    assert created.status_code == HTTPStatus.ACCEPTED
    denied = api_harness.client.get(f"/v1/import-runs/{created.json()['runId']}/artifacts")
    assert denied.status_code == HTTPStatus.UNAUTHORIZED
    assert "raw-imports" not in denied.text
    assert "derived-artifacts" not in denied.text


def test_import_run_creation_enqueues_without_inline_import_execution(
    api_harness: ApiHarness,
) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)
    store_credentials(api_harness.client, api_harness.headers, league_id)
    created = api_harness.client.post(
        f"/v1/leagues/{league_id}/import-runs",
        headers=api_harness.headers,
        json={
            "startYear": 2020,
            "endYear": 2025,
            "includeActivity": True,
            "forceRefresh": False,
        },
    )
    payload = created.json()
    assert created.status_code == HTTPStatus.ACCEPTED
    assert payload["status"] == "queued"
    assert payload["step"] == "queued"
    assert payload["sourceCounts"]["canonicalTradeEvents"] == CANONICAL_TRADE_EVENTS
    assert payload["errorSummary"] is None
    assert "succeeded" not in created.text
