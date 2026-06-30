from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mygm_worker.analytics import write_snapshot_artifacts
from mygm_worker.jobs.evidence import write_evidence
from mygm_worker.jobs.locks import LocalRunStore
from mygm_worker.jobs.models import (
    CurrentVersionPointer,
    ImportRun,
    JobStatus,
    LeagueId,
    StepName,
    StepStatus,
    TenantId,
    TransformVersion,
    now_iso,
)
from mygm_worker.jobs.storage import (
    DERIVED_ARTIFACTS_BUCKET,
    RAW_IMPORTS_BUCKET,
    artifact_metadata,
    derived_artifact_prefix,
    raw_import_prefix,
    source_documents,
)

DEFAULT_TRANSFORM_VERSION = TransformVersion("retrospective-v1")


@dataclass(frozen=True, slots=True)
class FixtureImportCommand:
    tenant_id: TenantId
    league_id: LeagueId
    fixture_root: Path
    evidence_path: Path
    state_root: Path
    transform_version: TransformVersion = DEFAULT_TRANSFORM_VERSION
    cancel_before_step: StepName | None = None


def run_fixture_import(command: FixtureImportCommand) -> ImportRun:
    run = ImportRun.create(
        tenant_id=command.tenant_id,
        league_id=command.league_id,
        fixture_root=command.fixture_root,
        transform_version=command.transform_version,
    )
    store = LocalRunStore(command.state_root)
    lock = store.acquire(command.tenant_id, command.league_id, run.identity.run_id)
    run.set_status(JobStatus.RUNNING)
    try:
        execute_steps(run, command)
    except RuntimeError:
        run.set_status(JobStatus.FAILED)
        lock = store.mark(lock, JobStatus.FAILED)
        raise
    else:
        lock = store.mark(lock, run.status)
    finally:
        _ = lock
        write_evidence(run, command.evidence_path)
    return run


def execute_steps(run: ImportRun, command: FixtureImportCommand) -> None:
    collect_sources(run, command)
    if stop_when_canceled(run, command, StepName("write_analytics_summary")):
        return
    summary_path, snapshot_path = write_analytics(run, command)
    if stop_when_canceled(run, command, StepName("publish_current_version")):
        return
    publish_current_version(run, summary_path, snapshot_path)
    run.set_status(JobStatus.SUCCEEDED)


def collect_sources(run: ImportRun, command: FixtureImportCommand) -> None:
    step = run.add_step(StepName("collect_source_documents"))
    step.start()
    run.source_documents = source_documents(command.fixture_root)
    raw_manifest = command.fixture_root / "export_manifest.json"
    run.artifacts.append(
        artifact_metadata(
            RAW_IMPORTS_BUCKET,
            f"{raw_import_prefix(run.identity)}export_manifest.json",
            raw_manifest,
        )
    )
    step.finish(StepStatus.SUCCEEDED)


def write_analytics(run: ImportRun, command: FixtureImportCommand) -> tuple[Path, Path]:
    step = run.add_step(StepName("write_analytics_summary"))
    step.start()
    output_dir = command.evidence_path.parent / f"{run.identity.run_id}-derived"
    summary_path, snapshot_path = write_snapshot_artifacts(
        command.fixture_root,
        output_dir,
        league_id=run.identity.league_id,
    )
    run.artifacts.append(
        artifact_metadata(
            DERIVED_ARTIFACTS_BUCKET,
            f"{derived_artifact_prefix(run.identity)}summary.json",
            summary_path,
        )
    )
    run.artifacts.append(
        artifact_metadata(
            DERIVED_ARTIFACTS_BUCKET,
            f"{derived_artifact_prefix(run.identity)}analytics_snapshot.json",
            snapshot_path,
        )
    )
    step.finish(StepStatus.SUCCEEDED)
    return summary_path, snapshot_path


def publish_current_version(run: ImportRun, summary_path: Path, snapshot_path: Path) -> None:
    step = run.add_step(StepName("publish_current_version"))
    step.start()
    summary_artifact_path = f"{derived_artifact_prefix(run.identity)}summary.json"
    snapshot_artifact_path = f"{derived_artifact_prefix(run.identity)}analytics_snapshot.json"
    run.current_version = CurrentVersionPointer(
        league_id=run.identity.league_id,
        import_run_id=run.identity.run_id,
        transform_version=run.identity.transform_version,
        derived_artifact_prefix=derived_artifact_prefix(run.identity),
        summary_artifact_path=summary_artifact_path,
        snapshot_artifact_path=snapshot_artifact_path,
        published_at=now_iso(),
    )
    _ = summary_path, snapshot_path
    step.finish(StepStatus.SUCCEEDED)


def stop_when_canceled(run: ImportRun, command: FixtureImportCommand, step_name: StepName) -> bool:
    if command.cancel_before_step != step_name:
        return False
    run.cancel_requested = True
    step = run.add_step(step_name)
    step.start()
    step.finish(StepStatus.CANCELED, "cancel_requested")
    run.set_status(JobStatus.CANCELED)
    return True
