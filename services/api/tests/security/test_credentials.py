from http import HTTPStatus
from typing import Final
from uuid import UUID

import pytest

from mygm_api.config import DEFAULT_DEV_KEY, Settings
from mygm_api.crypto import CredentialEncryptor, CredentialSecret, InvalidCredentialKeyError
from mygm_api.models import LeagueId
from mygm_api.security import UserId
from tests.conftest import ApiHarness
from tests.contracts.test_all_declared_endpoints import create_authorized_league

ROTATED_VERSION: Final[int] = 2


def test_credentials_are_encrypted_and_plaintext_never_returns_when_stored(
    api_harness: ApiHarness,
) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)
    response = api_harness.client.post(
        f"/v1/leagues/{league_id}/credentials",
        headers=api_harness.headers,
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
    assert response.json()["credentialVersion"] == 1
    forbidden = ("{TEST-SWID}", "test-token", "espn_s2", "SWID", "ciphertext", "nonce")
    for value in forbidden:
        assert value not in response.text
    stored = api_harness.store.credentials[LeagueId(UUID(league_id))]
    assert stored.ciphertext != ""
    assert stored.nonce != ""
    assert "{TEST-SWID}" not in repr(stored)
    assert "test-token" not in repr(stored)
    assert "{TEST-SWID}" not in repr(CredentialSecret(swid="{TEST-SWID}", espn_s2="test-token"))
    assert "test-token" not in repr(CredentialSecret(swid="{TEST-SWID}", espn_s2="test-token"))


def test_credential_rotation_increments_version_and_records_consent_when_reposted(
    api_harness: ApiHarness,
) -> None:
    league_id = create_authorized_league(api_harness.client, api_harness.headers)
    first = store_credential(api_harness, league_id, "consent-v1")
    second = store_credential(api_harness, league_id, "consent-v2")
    assert first["credentialVersion"] == 1
    assert second["credentialVersion"] == ROTATED_VERSION
    assert second["consentVersion"] == "consent-v2"
    assert second["rotatedAt"] is not None


def test_settings_accept_mygm_credential_key_v1_when_loading_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MYGM_CREDENTIAL_KEY_V1", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    settings = Settings()
    assert settings.credential_key == "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


def test_settings_ignore_non_contract_credential_key_alias_when_loading_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MYGM_CREDENTIAL_KEY_V1", raising=False)
    monkeypatch.setenv("MYGM_API_CREDENTIAL_KEY_V1", "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=")
    settings = Settings()
    assert settings.credential_key != "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB="


def test_encryptor_rejects_invalid_decoded_key_length_when_key_is_misconfigured() -> None:
    encryptor = CredentialEncryptor(key_id="bad", encoded_key="AAAA")
    with pytest.raises(InvalidCredentialKeyError):
        _ = encryptor.encrypt(
            league_id=LeagueId(UUID(int=1)),
            credential_version=1,
            consent_version="alpha",
            created_by=UserId("user-1"),
            secret=CredentialSecret(swid="{TEST-SWID}", espn_s2="test-token"),
        )


def test_encryptor_accepts_unpadded_urlsafe_base64_key() -> None:
    encryptor = CredentialEncryptor(key_id="alpha", encoded_key=DEFAULT_DEV_KEY.rstrip("="))
    credential = encryptor.encrypt(
        league_id=LeagueId(UUID(int=1)),
        credential_version=1,
        consent_version="alpha",
        created_by=UserId("user-1"),
        secret=CredentialSecret(swid="{TEST-SWID}", espn_s2="test-token"),
    )

    assert credential.ciphertext != ""
    assert credential.nonce != ""


def store_credential(
    api_harness: ApiHarness,
    league_id: str,
    consent_version: str,
) -> dict[str, int | str]:
    response = api_harness.client.post(
        f"/v1/leagues/{league_id}/credentials",
        headers=api_harness.headers,
        json={
            "leagueId": league_id,
            "SWID": "{TEST-SWID}",
            "espn_s2": "test-token",
            "consentVersion": consent_version,
            "startYear": 2020,
            "endYear": 2025,
        },
    )
    assert response.status_code == HTTPStatus.OK
    return response.json()
