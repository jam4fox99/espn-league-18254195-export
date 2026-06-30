from __future__ import annotations

import os

from mygm_worker.jobs.credentials import (
    CredentialStatus,
    decrypt_credential,
    encrypt_for_test,
)


def test_decrypt_credential_returns_plaintext_in_memory_when_key_matches() -> None:
    os.environ["MYGM_CREDENTIAL_KEY_V1"] = "unit-test-key"
    ciphertext = encrypt_for_test("unit-test-key", "v1", "nonce", "opaque-token")

    result = decrypt_credential(ciphertext)

    assert result.status is CredentialStatus.AVAILABLE
    assert result.key_id == "v1"
    assert result.plaintext == "opaque-token"


def test_decrypt_credential_reports_missing_key_without_plaintext() -> None:
    _ = os.environ.pop("MYGM_CREDENTIAL_KEY_V1", None)
    ciphertext = encrypt_for_test("unit-test-key", "v1", "nonce", "opaque-token")

    result = decrypt_credential(ciphertext)

    assert result.status is CredentialStatus.MISSING_KEY
    assert result.plaintext is None
