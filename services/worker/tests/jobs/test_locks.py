from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mygm_worker.jobs.locks import DuplicateRunError, LocalRunStore, lock_to_json
from mygm_worker.jobs.models import JobStatus, LeagueId, RunId, TenantId


def test_duplicate_lock_blocks_active_run_when_heartbeat_is_fresh(tmp_path: Path) -> None:
    store = LocalRunStore(tmp_path, stale_after_seconds=60)
    first = store.acquire(TenantId("tenant"), LeagueId("league"), RunId("run-1"))

    with pytest.raises(DuplicateRunError):
        _ = store.acquire(first.tenant_id, first.league_id, RunId("run-2"))


def test_stale_lock_is_taken_over_when_heartbeat_is_old(tmp_path: Path) -> None:
    store = LocalRunStore(tmp_path, stale_after_seconds=1)
    first = store.acquire(TenantId("tenant"), LeagueId("league"), RunId("run-1"))
    stale = {
        "tenant_id": first.tenant_id,
        "league_id": first.league_id,
        "run_id": first.run_id,
        "status": first.status,
        "heartbeat_at": (datetime.now(UTC) - timedelta(seconds=30)).isoformat(),
    }
    _ = store.lock_path(first.tenant_id, first.league_id).write_text(
        json.dumps(stale),
        encoding="utf-8",
    )

    second = store.acquire(first.tenant_id, first.league_id, RunId("run-2"))

    assert second.run_id == "run-2"


def test_dead_run_lock_allows_retry_when_marked_dead(tmp_path: Path) -> None:
    store = LocalRunStore(tmp_path)
    first = store.acquire(TenantId("tenant"), LeagueId("league"), RunId("run-1"))
    dead = store.mark(first, JobStatus.DEAD)
    _ = store.lock_path(dead.tenant_id, dead.league_id).write_text(
        lock_to_json(dead),
        encoding="utf-8",
    )

    second = store.acquire(dead.tenant_id, dead.league_id, RunId("run-2"))

    assert second.run_id == "run-2"
