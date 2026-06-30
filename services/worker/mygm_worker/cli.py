from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from mygm_worker.analytics import write_snapshot_artifacts
from mygm_worker.jobs import FixtureImportCommand, run_fixture_import
from mygm_worker.jobs.fixture_import import DEFAULT_TRANSFORM_VERSION
from mygm_worker.jobs.models import LeagueId, StepName, TenantId, TransformVersion


@dataclass(slots=True)
class WorkerArgs(argparse.Namespace):
    command: Literal["analyze-fixture", "import-fixture"] = "analyze-fixture"
    fixture_root: str = ""
    out: str = ""
    evidence: str = ""
    league_id: str = ""
    tenant_id: str = ""
    state_root: str = ".mygm-worker-runs"
    transform_version: str = DEFAULT_TRANSFORM_VERSION
    cancel_before_step: str | None = None


def parse_args() -> WorkerArgs:
    parser = argparse.ArgumentParser(prog="mygm-worker")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze-fixture")
    _ = analyze.add_argument("--fixture-root", required=True)
    _ = analyze.add_argument("--out", required=True)
    import_fixture = subparsers.add_parser("import-fixture")
    _ = import_fixture.add_argument("--league-id", required=True)
    _ = import_fixture.add_argument("--fixture-root", required=True)
    _ = import_fixture.add_argument("--tenant-id", required=True)
    _ = import_fixture.add_argument("--evidence", required=True)
    _ = import_fixture.add_argument("--state-root", default=".mygm-worker-runs")
    _ = import_fixture.add_argument("--transform-version", default=DEFAULT_TRANSFORM_VERSION)
    _ = import_fixture.add_argument("--cancel-before-step", default=None)
    namespace = WorkerArgs()
    _ = parser.parse_args(namespace=namespace)
    return namespace


def main() -> int:
    args = parse_args()
    match args.command:
        case "analyze-fixture":
            fixture_root = Path(args.fixture_root)
            output_root = Path(args.out)
            _summary_path, snapshot_path = write_snapshot_artifacts(fixture_root, output_root)
            print(snapshot_path)
            return 0
        case "import-fixture":
            command = FixtureImportCommand(
                tenant_id=TenantId(args.tenant_id),
                league_id=LeagueId(args.league_id),
                fixture_root=Path(args.fixture_root),
                evidence_path=Path(args.evidence),
                state_root=Path(args.state_root),
                transform_version=TransformVersion(args.transform_version),
                cancel_before_step=cancel_step(args.cancel_before_step),
            )
            run = run_fixture_import(command)
            print(run.status)
            return 0


def cancel_step(value: str | None) -> StepName | None:
    if value is None:
        return None
    return StepName(value)


if __name__ == "__main__":
    raise SystemExit(main())
