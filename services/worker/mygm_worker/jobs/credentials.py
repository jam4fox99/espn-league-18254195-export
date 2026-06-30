from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from enum import StrEnum


class CredentialStatus(StrEnum):
    AVAILABLE = "available"
    MISSING_KEY = "missing_key"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class CredentialCiphertext:
    key_id: str
    nonce: str
    ciphertext: str
    tag: str


@dataclass(frozen=True, slots=True)
class DecryptionResult:
    status: CredentialStatus
    key_id: str | None = None
    plaintext: str | None = None


def decrypt_credential(metadata: CredentialCiphertext) -> DecryptionResult:
    key = os.environ.get("MYGM_CREDENTIAL_KEY_V1")
    if key is None:
        return DecryptionResult(CredentialStatus.MISSING_KEY, metadata.key_id)
    plaintext = xor_bytes(
        base64.b64decode(metadata.ciphertext),
        key_stream(key.encode(), metadata.nonce.encode()),
    ).decode("utf-8")
    expected = credential_tag(key, metadata.nonce, plaintext)
    if not hmac.compare_digest(expected, metadata.tag):
        return DecryptionResult(CredentialStatus.INVALID, metadata.key_id)
    return DecryptionResult(CredentialStatus.AVAILABLE, metadata.key_id, plaintext)


def encrypt_for_test(key: str, key_id: str, nonce: str, plaintext: str) -> CredentialCiphertext:
    encrypted = xor_bytes(plaintext.encode(), key_stream(key.encode(), nonce.encode()))
    return CredentialCiphertext(
        key_id=key_id,
        nonce=nonce,
        ciphertext=base64.b64encode(encrypted).decode("ascii"),
        tag=credential_tag(key, nonce, plaintext),
    )


def credential_tag(key: str, nonce: str, plaintext: str) -> str:
    return hmac.new(
        key.encode(),
        nonce.encode() + b":" + plaintext.encode(),
        hashlib.sha256,
    ).hexdigest()


def key_stream(key: bytes, nonce: bytes) -> bytes:
    return hashlib.sha256(key + b":" + nonce).digest()


def xor_bytes(payload: bytes, key: bytes) -> bytes:
    return bytes(value ^ key[index % len(key)] for index, value in enumerate(payload))
