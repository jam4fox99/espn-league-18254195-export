from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mygm_worker.jobs.models import (
        ArtifactMetadata,
        CurrentVersionPointer,
        ImportRun,
        ImportStep,
        SourceDocument,
    )


def write_evidence(run: ImportRun, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(run_payload(run), indent=2, sort_keys=True), encoding="utf-8")


def run_payload(run: ImportRun) -> dict[str, object]:
    return {
        "status": run.status,
        "tenant_id": run.identity.tenant_id,
        "league_id": run.identity.league_id,
        "import_run_id": run.identity.run_id,
        "transform_version": run.identity.transform_version,
        "fixture_root": str(run.fixture_root),
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "steps": [step_payload(step) for step in run.steps],
        "source_documents": [source_payload(document) for document in run.source_documents],
        "artifacts": [artifact_payload(artifact) for artifact in run.artifacts],
        "current_version": current_version_payload(run.current_version),
    }


def step_payload(step: ImportStep) -> dict[str, object]:
    return {
        "name": step.name,
        "status": step.status,
        "attempts": step.attempts,
        "started_at": step.started_at,
        "finished_at": step.finished_at,
        "error_code": step.error_code,
    }


def source_payload(document: SourceDocument) -> dict[str, object]:
    return {
        "path": document.path,
        "sha256": document.sha256,
        "size_bytes": document.size_bytes,
    }


def artifact_payload(artifact: ArtifactMetadata) -> dict[str, object]:
    return {
        "bucket": artifact.bucket,
        "path": artifact.path,
        "sha256": artifact.sha256,
        "size_bytes": artifact.size_bytes,
        "content_type": artifact.content_type,
    }


def current_version_payload(pointer: CurrentVersionPointer | None) -> dict[str, object] | None:
    if pointer is None:
        return None
    return {
        "league_id": pointer.league_id,
        "import_run_id": pointer.import_run_id,
        "transform_version": pointer.transform_version,
        "derived_artifact_prefix": pointer.derived_artifact_prefix,
        "summary_artifact_path": pointer.summary_artifact_path,
        "snapshot_artifact_path": pointer.snapshot_artifact_path,
        "published_at": pointer.published_at,
    }
