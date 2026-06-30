from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import NewType
from uuid import UUID, uuid4

from mygm_api.security import UserId

LeagueId = NewType("LeagueId", UUID)
RunId = NewType("RunId", UUID)
VersionId = NewType("VersionId", UUID)


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    DEAD = "dead"


class CredentialStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ClaimStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class League:
    id: LeagueId
    org_id: UUID
    espn_league_id: str
    name: str
    created_by: UserId


@dataclass(frozen=True, slots=True)
class EncryptedCredential:
    league_id: LeagueId
    credential_version: int
    key_id: str
    nonce: str
    ciphertext: str
    expires_at: datetime
    rotated_at: datetime | None
    last_validated_at: datetime | None
    status: CredentialStatus
    consent_version: str
    authorized_by: UserId
    created_by: UserId


@dataclass(frozen=True, slots=True)
class ManagerClaim:
    id: UUID
    league_id: LeagueId
    espn_team_id: str
    status: ClaimStatus
    requested_by: UserId


@dataclass(frozen=True, slots=True)
class ShareLink:
    id: UUID
    league_id: LeagueId
    version_id: VersionId
    slug: str
    revoked: bool


@dataclass(frozen=True, slots=True)
class ImportRun:
    id: RunId
    league_id: LeagueId
    requested_by: UserId
    status: RunStatus
    credential_version: int
    idempotency_key: str | None
    step: str = "queued"
    warnings: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def new_league_id() -> LeagueId:
    return LeagueId(uuid4())


def new_run_id() -> RunId:
    return RunId(uuid4())


def default_credential_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=90)
