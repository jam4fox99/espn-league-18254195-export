from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import NewType
from uuid import uuid4

TenantId = NewType("TenantId", str)
LeagueId = NewType("LeagueId", str)
RunId = NewType("RunId", str)
StepName = NewType("StepName", str)
TransformVersion = NewType("TransformVersion", str)


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    DEAD = "dead"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELED = "canceled"


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class ImportIdentity:
    tenant_id: TenantId
    league_id: LeagueId
    run_id: RunId
    transform_version: TransformVersion


@dataclass(frozen=True, slots=True)
class ArtifactMetadata:
    bucket: str
    path: str
    sha256: str
    size_bytes: int
    content_type: str


@dataclass(frozen=True, slots=True)
class SourceDocument:
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class CurrentVersionPointer:
    league_id: LeagueId
    import_run_id: RunId
    transform_version: TransformVersion
    derived_artifact_prefix: str
    summary_artifact_path: str
    snapshot_artifact_path: str
    published_at: str


@dataclass(slots=True)
class ImportStep:
    name: StepName
    status: StepStatus = StepStatus.PENDING
    attempts: int = 0
    started_at: str | None = None
    finished_at: str | None = None
    error_code: str | None = None

    def start(self) -> None:
        self.status = StepStatus.RUNNING
        self.attempts += 1
        self.started_at = now_iso()

    def finish(self, status: StepStatus, error_code: str | None = None) -> None:
        self.status = status
        self.error_code = error_code
        self.finished_at = now_iso()


@dataclass(slots=True)
class ImportRun:
    identity: ImportIdentity
    fixture_root: Path
    status: JobStatus = JobStatus.PENDING
    steps: list[ImportStep] = field(default_factory=list)
    source_documents: list[SourceDocument] = field(default_factory=list)
    artifacts: list[ArtifactMetadata] = field(default_factory=list)
    current_version: CurrentVersionPointer | None = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    cancel_requested: bool = False

    @classmethod
    def create(
        cls,
        tenant_id: TenantId,
        league_id: LeagueId,
        fixture_root: Path,
        transform_version: TransformVersion,
    ) -> ImportRun:
        run_id = RunId(uuid4().hex)
        identity = ImportIdentity(tenant_id, league_id, run_id, transform_version)
        return cls(identity=identity, fixture_root=fixture_root)

    def set_status(self, status: JobStatus) -> None:
        self.status = status
        self.updated_at = now_iso()

    def add_step(self, name: StepName) -> ImportStep:
        step = ImportStep(name=name)
        self.steps.append(step)
        return step
