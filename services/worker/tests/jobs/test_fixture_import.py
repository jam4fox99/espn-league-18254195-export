from __future__ import annotations

# pyright: reportAny=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
import json
from pathlib import Path

from mygm_worker.jobs import FixtureImportCommand, JobStatus, run_fixture_import
from mygm_worker.jobs.models import LeagueId, StepName, TenantId


def fixture_root() -> Path:
    return Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "espn" / "league_18254195"


def load_json(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        message = "Expected JSON object"
        raise TypeError(message)
    return data


def test_import_fixture_writes_succeeded_evidence_when_fixture_is_valid(tmp_path: Path) -> None:
    evidence = tmp_path / "task-5-mygm-espn-private-alpha.json"

    run = run_fixture_import(
        FixtureImportCommand(
            tenant_id=TenantId("tenant_test"),
            league_id=LeagueId("18254195"),
            fixture_root=fixture_root(),
            evidence_path=evidence,
            state_root=tmp_path / "runs",
        )
    )

    payload = load_json(evidence)
    assert run.status is JobStatus.SUCCEEDED
    assert payload["status"] == "succeeded"
    assert payload["league_id"] == "18254195"
    assert payload["tenant_id"] == "tenant_test"
    assert terminal_step_statuses(payload) == [
        "succeeded",
        "succeeded",
        "succeeded",
    ]
    assert raw_manifest_path(payload).startswith(
        "org/tenant_test/league/18254195/import/"
    )
    assert "/transform/retrospective-v1/summary.json" in derived_summary_path(payload)
    assert "/transform/retrospective-v1/analytics_snapshot.json" in derived_snapshot_path(payload)
    assert current_version(payload)["summary_artifact_path"] == derived_summary_path(payload)
    assert current_version(payload)["snapshot_artifact_path"] == derived_snapshot_path(payload)
    assert source_hashes(payload)["export_manifest.json"]


def test_import_fixture_writes_canceled_evidence_when_cancel_requested(tmp_path: Path) -> None:
    evidence = tmp_path / "canceled.json"

    run = run_fixture_import(
        FixtureImportCommand(
            tenant_id=TenantId("tenant_test"),
            league_id=LeagueId("18254195"),
            fixture_root=fixture_root(),
            evidence_path=evidence,
            state_root=tmp_path / "runs",
            cancel_before_step=StepName("write_analytics_summary"),
        )
    )

    payload = load_json(evidence)
    assert run.status is JobStatus.CANCELED
    assert payload["status"] == "canceled"
    assert terminal_step_statuses(payload) == ["succeeded", "canceled"]
    assert payload["current_version"] is None


def terminal_step_statuses(payload: dict[str, object]) -> list[str]:
    steps = payload["steps"]
    if not isinstance(steps, list):
        message = "Expected steps list"
        raise TypeError(message)
    return [
        step["status"]
        for step in steps
        if isinstance(step, dict) and isinstance(step.get("status"), str)
    ]


def raw_manifest_path(payload: dict[str, object]) -> str:
    return artifact_path(payload, "raw-imports")


def derived_summary_path(payload: dict[str, object]) -> str:
    return artifact_path(payload, "derived-artifacts", "summary.json")


def derived_snapshot_path(payload: dict[str, object]) -> str:
    return artifact_path(payload, "derived-artifacts", "analytics_snapshot.json")


def artifact_path(payload: dict[str, object], bucket: str, suffix: str | None = None) -> str:
    artifacts = payload["artifacts"]
    if not isinstance(artifacts, list):
        message = "Expected artifacts list"
        raise TypeError(message)
    for artifact in artifacts:
        if isinstance(artifact, dict) and artifact.get("bucket") == bucket:
            path = artifact.get("path")
            if isinstance(path, str) and (suffix is None or path.endswith(suffix)):
                return path
    message = f"Missing artifact in {bucket}"
    raise AssertionError(message)


def current_version(payload: dict[str, object]) -> dict[str, object]:
    pointer = payload["current_version"]
    if isinstance(pointer, dict):
        return pointer
    message = "Expected current version pointer"
    raise TypeError(message)


def source_hashes(payload: dict[str, object]) -> dict[str, str]:
    documents = payload["source_documents"]
    if not isinstance(documents, list):
        message = "Expected source documents list"
        raise TypeError(message)
    hashes: dict[str, str] = {}
    for document in documents:
        if isinstance(document, dict):
            path = document.get("path")
            sha256 = document.get("sha256")
            if isinstance(path, str) and isinstance(sha256, str):
                hashes[path] = sha256
    return hashes
