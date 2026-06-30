import base64
import binascii
from dataclasses import dataclass
from datetime import UTC, datetime
from secrets import token_bytes
from typing import Final, override

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from mygm_api.models import (
    CredentialStatus,
    EncryptedCredential,
    LeagueId,
    default_credential_expiry,
)
from mygm_api.security import UserId

NONCE_BYTES: Final[int] = 12
AES_KEY_BYTES: Final[frozenset[int]] = frozenset({16, 24, 32})


@dataclass(frozen=True, slots=True, repr=False)
class CredentialSecret:
    swid: str
    espn_s2: str


@dataclass(frozen=True, slots=True)
class InvalidCredentialKeyError(Exception):
    decoded_length: int

    @override
    def __str__(self) -> str:
        return f"credential key must decode to 16, 24, or 32 bytes; got {self.decoded_length}"


@dataclass(frozen=True, slots=True)
class CredentialEncryptor:
    key_id: str
    encoded_key: str

    def encrypt(
        self,
        league_id: LeagueId,
        credential_version: int,
        consent_version: str,
        created_by: UserId,
        secret: CredentialSecret,
    ) -> EncryptedCredential:
        key = decode_credential_key(self.encoded_key)
        nonce = token_bytes(NONCE_BYTES)
        plaintext = f"{secret.swid}\n{secret.espn_s2}".encode()
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
        return EncryptedCredential(
            league_id=league_id,
            credential_version=credential_version,
            key_id=self.key_id,
            nonce=base64.urlsafe_b64encode(nonce).decode(),
            ciphertext=base64.urlsafe_b64encode(ciphertext).decode(),
            expires_at=default_credential_expiry(),
            rotated_at=datetime.now(UTC) if credential_version > 1 else None,
            last_validated_at=None,
            status=CredentialStatus.ACTIVE,
            consent_version=consent_version,
            authorized_by=created_by,
            created_by=created_by,
        )


def decode_credential_key(encoded_key: str) -> bytes:
    padded_key = f"{encoded_key}{'=' * (-len(encoded_key) % 4)}"
    try:
        key = base64.urlsafe_b64decode(padded_key)
    except binascii.Error as exc:
        raise InvalidCredentialKeyError(decoded_length=0) from exc
    if len(key) not in AES_KEY_BYTES:
        raise InvalidCredentialKeyError(decoded_length=len(key))
    return key
