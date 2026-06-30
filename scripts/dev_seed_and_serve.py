#!/usr/bin/env python3
"""Seed the in-memory API store with the local ESPN fixture snapshot, then serve it.

The API keeps all state in memory (no database), so a freshly booted server has no
leagues and every dashboard request 409s with "analytics snapshot required". This
script injects the pre-built league_18254195 analytics snapshot for the demo league
UUID that the web homepage's "View dashboard" button points at, and grants the
hard-coded local alpha user (local-alpha-user) access — so the running web app shows
a fully populated dashboard without any live ESPN credentials.

Data is in memory: restarting the server resets it (re-run this script to reseed).

Usage (from repo root):
    cd services/api && uv run python ../../scripts/dev_seed_and_serve.py
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]

# Dev-only API settings must exist before importing the app (CORS + credential key
# are read at import time). Real deployments override these via the environment.
os.environ.setdefault("MYGM_CREDENTIAL_KEY_V1", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
os.environ.setdefault("MYGM_CREDENTIAL_KEY_ID", "local-dev-1")
os.environ.setdefault("MYGM_ALLOWED_ORIGINS", '["http://127.0.0.1:3000"]')

import uvicorn  # noqa: E402

from mygm_api.dependencies import store  # noqa: E402  -- the singleton the app serves from
from mygm_api.main import app  # noqa: E402
from mygm_api.models import League, LeagueId, VersionId  # noqa: E402
from mygm_api.schemas import LeagueAnalyticsSnapshotResponse  # noqa: E402
from mygm_api.security import UserId  # noqa: E402

# Matches apps/web/lib/session.ts (local alpha session) and the homepage demo link.
ALPHA_USER = UserId("local-alpha-user")
DEMO_LEAGUE = LeagueId(UUID("11111111-1111-4111-8111-111111111111"))
SNAPSHOT_PATH = ROOT / "tests" / "fixtures" / "espn" / "league_18254195" / "analytics_snapshot.json"

HOST = os.environ.get("MYGM_DEV_HOST", "127.0.0.1")
PORT = int(os.environ.get("MYGM_DEV_PORT", "8000"))


def seed() -> None:
    store.accept_invite(ALPHA_USER)
    store.leagues[DEMO_LEAGUE] = League(
        id=DEMO_LEAGUE,
        org_id=uuid4(),
        espn_league_id="18254195",
        name="Demo Dynasty League",
        created_by=ALPHA_USER,
    )
    store.memberships[DEMO_LEAGUE] = {ALPHA_USER}
    snapshot = LeagueAnalyticsSnapshotResponse.model_validate_json(
        SNAPSHOT_PATH.read_text(encoding="utf-8")
    )
    version_id = VersionId(uuid4())
    store.analytics_snapshots[(DEMO_LEAGUE, version_id)] = snapshot
    store.current_analytics_version_by_league[DEMO_LEAGUE] = version_id


def main() -> None:
    if not SNAPSHOT_PATH.exists():
        raise SystemExit(
            f"snapshot not found: {SNAPSHOT_PATH}\n"
            "Regenerate it with: cd services/worker && uv run mygm-worker analyze-fixture "
            "--fixture-root ../../tests/fixtures/espn/league_18254195 "
            "--out ../../tests/fixtures/espn/league_18254195"
        )
    seed()
    print(f"Seeded demo league {DEMO_LEAGUE} for {ALPHA_USER}")
    print(f"API:        http://{HOST}:{PORT}")
    print("Web home:   http://127.0.0.1:3000  (click 'View dashboard')")
    print(f"Direct:     http://127.0.0.1:3000/leagues/{DEMO_LEAGUE}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
