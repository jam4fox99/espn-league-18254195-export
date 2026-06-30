from __future__ import annotations

# pyright: reportAny=false, reportUnknownArgumentType=false
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mygm_worker.jobs.models import JobStatus, LeagueId, RunId, TenantId, now_iso


@dataclass(frozen=True, slots=True)
class LockRecord:
    tenant_id: TenantId
    league_id: LeagueId
    run_id: RunId
    status: JobStatus
    heartbeat_at: str


class DuplicateRunError(RuntimeError):
    def __init__(self, record: LockRecord) -> None:
        super().__init__("active import already exists")
        self.record: LockRecord = record


class LocalRunStore:
    def __init__(self, root: Path, stale_after_seconds: int = 900) -> None:
        self.root: Path = root
        self.stale_after: timedelta = timedelta(seconds=stale_after_seconds)

    def acquire(self, tenant_id: TenantId, league_id: LeagueId, run_id: RunId) -> LockRecord:
        self.root.mkdir(parents=True, exist_ok=True)
        existing = self.read_lock(tenant_id, league_id)
        if existing is not None and not self.can_take_over(existing):
            raise DuplicateRunError(existing)
        record = LockRecord(
            tenant_id=tenant_id,
            league_id=league_id,
            run_id=run_id,
            status=JobStatus.RUNNING,
            heartbeat_at=now_iso(),
        )
        _ = self.lock_path(tenant_id, league_id).write_text(
            lock_to_json(record),
            encoding="utf-8",
        )
        return record

    def mark(self, record: LockRecord, status: JobStatus) -> LockRecord:
        next_record = LockRecord(
            tenant_id=record.tenant_id,
            league_id=record.league_id,
            run_id=record.run_id,
            status=status,
            heartbeat_at=now_iso(),
        )
        _ = self.lock_path(record.tenant_id, record.league_id).write_text(
            lock_to_json(next_record),
            encoding="utf-8",
        )
        return next_record

    def read_lock(self, tenant_id: TenantId, league_id: LeagueId) -> LockRecord | None:
        path = self.lock_path(tenant_id, league_id)
        if not path.exists():
            return None
        return lock_from_json(path.read_text(encoding="utf-8"))

    def can_take_over(self, record: LockRecord) -> bool:
        terminal_statuses = {
            JobStatus.SUCCEEDED,
            JobStatus.FAILED,
            JobStatus.CANCELED,
            JobStatus.DEAD,
        }
        if record.status in terminal_statuses:
            return True
        heartbeat = datetime.fromisoformat(record.heartbeat_at)
        return datetime.now(UTC) - heartbeat > self.stale_after

    def lock_path(self, tenant_id: TenantId, league_id: LeagueId) -> Path:
        return self.root / f"{tenant_id}-{league_id}.lock.json"


def lock_to_json(record: LockRecord) -> str:
    payload = {
        "tenant_id": record.tenant_id,
        "league_id": record.league_id,
        "run_id": record.run_id,
        "status": record.status,
        "heartbeat_at": record.heartbeat_at,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def lock_from_json(payload: str) -> LockRecord:
    data = json.loads(payload)
    if not isinstance(data, dict):
        message = "Expected lock JSON object"
        raise TypeError(message)
    return LockRecord(
        tenant_id=TenantId(require_str(data, "tenant_id")),
        league_id=LeagueId(require_str(data, "league_id")),
        run_id=RunId(require_str(data, "run_id")),
        status=JobStatus(require_str(data, "status")),
        heartbeat_at=require_str(data, "heartbeat_at"),
    )


def require_str(data: dict[object, object], key: str) -> str:
    value = data.get(key)
    if isinstance(value, str):
        return value
    message = f"Expected string lock field {key}"
    raise TypeError(message)
