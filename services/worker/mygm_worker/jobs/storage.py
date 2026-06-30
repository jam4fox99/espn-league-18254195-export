from __future__ import annotations

import hashlib
from pathlib import Path

from mygm_worker.jobs.models import (
    ArtifactMetadata,
    ImportIdentity,
    SourceDocument,
)

RAW_IMPORTS_BUCKET = "raw-imports"
DERIVED_ARTIFACTS_BUCKET = "derived-artifacts"


def raw_import_prefix(identity: ImportIdentity) -> str:
    return (
        f"org/{identity.tenant_id}/league/{identity.league_id}/"
        f"import/{identity.run_id}/"
    )


def derived_artifact_prefix(identity: ImportIdentity) -> str:
    return (
        f"league/{identity.league_id}/source_import/{identity.run_id}/"
        f"transform/{identity.transform_version}/"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_documents(fixture_root: Path) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    for path in sorted(fixture_root.rglob("*.json")):
        relative = path.relative_to(fixture_root).as_posix()
        documents.append(
            SourceDocument(
                path=relative,
                sha256=sha256_file(path),
                size_bytes=path.stat().st_size,
            )
        )
    return documents


def artifact_metadata(bucket: str, path: str, local_path: Path) -> ArtifactMetadata:
    return ArtifactMetadata(
        bucket=bucket,
        path=path,
        sha256=sha256_file(local_path),
        size_bytes=local_path.stat().st_size,
        content_type="application/json",
    )
