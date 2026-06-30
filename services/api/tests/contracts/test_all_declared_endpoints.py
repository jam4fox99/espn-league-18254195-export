from http import HTTPStatus
from typing import Final
from uuid import UUID

from fastapi.testclient import TestClient

from tests.conftest import ApiHarness

EXPECTED_PATHS: Final[set[str]] = {
    "/v1/me",
    "/v1/alpha-invites/accept",
    "/v1/organizations/{organization_id}/leagues",
    "/v1/manager-claims",
    "/v1/manager-claims/{claim_id}",
    "/v1/leagues",
    "/v1/leagues/{league_id}",
    "/v1/leagues/{league_id}/credentials",
    "/v1/leagues/{league_id}/credentials/validate",
    "/v1/leagues/{league_id}/import-runs",
    "/v1/import-runs/{run_id}",
    "/v1/import-runs/{run_id}/artifacts",
    "/v1/import-runs/{run_id}/cancel",
    "/v1/import-runs/{run_id}/retry",
    "/v1/leagues/{league_id}/reprocess-runs",
    "/v1/reprocess-runs/{run_id}",
    "/v1/versions/{version_id}/publish",
    "/v1/admin/import-runs",
    "/v1/leagues/{league_id}/dashboard",
    "/v1/leagues/{league_id}/seasons",
    "/v1/leagues/{league_id}/seasons/{season_year}",
    "/v1/leagues/{league_id}/leaderboard",
    "/v1/leagues/{league_id}/gms",
    "/v1/leagues/{league_id}/gms/{manager_id}",
    "/v1/leagues/{league_id}/trades",
    "/v1/leagues/{league_id}/trades/{trade_id}",
    "/v1/leagues/{league_id}/waivers",
    "/v1/leagues/{league_id}/waivers/{waiver_id}",
    "/v1/leagues/{league_id}/records",
    "/v1/leagues/{league_id}/head-to-head",
    "/v1/leagues/{league_id}/formula",
    "/v1/leagues/{league_id}/data-health",
    "/v1/leagues/{league_id}/players/{player_id}/weekly-points",
    "/v1/leagues/{league_id}/share-links",
    "/v1/share-links/{share_link_id}",
    "/v1/share/{share_slug}",
    "/v1/share/{share_slug}/og.png",
}


def test_openapi_exposes_frozen_contract_paths_when_schema_is_generated(
    api_harness: ApiHarness,
) -> None:
    response = api_harness.client.get("/openapi.json")
    assert response.status_code == HTTPStatus.OK
    paths = set(response.json()["paths"])
    assert paths >= EXPECTED_PATHS
    assert "/v1/invites/accept" not in paths


def test_protected_routes_reject_missing_bearer_token_when_unauthenticated(
    api_harness: ApiHarness,
) -> None:
    response = api_harness.client.get(f"/v1/leagues/{UUID(int=1)}/gms")
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert "compositeScore" not in response.text


def test_endpoint_flow_covers_auth_membership_and_job_shapes_when_authorized(
    api_harness: ApiHarness,
) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)
    store_credentials(api_harness.client, api_harness.headers, league_id)
    first = api_harness.client.post(
        f"/v1/leagues/{league_id}/import-runs",
        headers={**api_harness.headers, "Idempotency-Key": "plan-fixture-1"},
        json={
            "startYear": 2020,
            "endYear": 2025,
            "includeActivity": True,
            "forceRefresh": False,
        },
    )
    second = api_harness.client.post(
        f"/v1/leagues/{league_id}/import-runs",
        headers={**api_harness.headers, "Idempotency-Key": "plan-fixture-1"},
        json={
            "startYear": 2020,
            "endYear": 2025,
            "includeActivity": True,
            "forceRefresh": False,
        },
    )
    assert first.status_code == HTTPStatus.ACCEPTED
    assert second.status_code == HTTPStatus.ACCEPTED
    assert first.json()["runId"] == second.json()["runId"]
    run_id = first.json()["runId"]
    status_response = api_harness.client.get(
        f"/v1/import-runs/{run_id}",
        headers=api_harness.headers,
    )
    artifact_response = api_harness.client.get(
        f"/v1/import-runs/{run_id}/artifacts",
        headers=api_harness.headers,
    )
    assert status_response.json()["status"] == "queued"
    assert artifact_response.json()["rawBucket"] == "raw-imports"
    assert "/raw" in artifact_response.json()["rawPrefix"]


def test_cancel_and_retry_preserve_original_created_at_when_run_status_changes(
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
    run_id = created.json()["runId"]
    cancelled = api_harness.client.post(
        f"/v1/import-runs/{run_id}/cancel",
        headers=api_harness.headers,
    )
    retried = api_harness.client.post(
        f"/v1/import-runs/{run_id}/retry",
        headers=api_harness.headers,
    )
    assert cancelled.json()["createdAt"] == created.json()["createdAt"]
    assert retried.json()["createdAt"] == created.json()["createdAt"]


def create_authorized_league(client: TestClient, headers: dict[str, str]) -> str:
    invite = client.post(
        "/v1/alpha-invites/accept",
        headers=headers,
        json={"email": "user@example.com", "inviteCode": "alpha"},
    )
    assert invite.status_code == HTTPStatus.OK
    league = client.post(
        "/v1/leagues",
        headers=headers,
        json={"espnLeagueId": "18254195", "name": "League of Record"},
    )
    assert league.status_code == HTTPStatus.CREATED
    return str(league.json()["leagueId"])


def store_credentials(client: TestClient, headers: dict[str, str], league_id: str) -> None:
    response = client.post(
        f"/v1/leagues/{league_id}/credentials",
        headers=headers,
        json={
            "leagueId": league_id,
            "SWID": "{TEST-SWID}",
            "espn_s2": "test-token",
            "consentVersion": "alpha-consent-v1",
            "startYear": 2020,
            "endYear": 2025,
        },
    )
    assert response.status_code == HTTPStatus.OK
