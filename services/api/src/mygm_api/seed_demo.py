"""Seed the in-memory store with the bundled demo-league snapshot.

Enabled in deployments by setting ``MYGM_SEED_DEMO=1`` so the public alpha API serves a
fully populated, read-only demo league for the hard-coded alpha user without any live
ESPN credentials. The store is in-memory, so each serverless cold start re-seeds
deterministically from the bundled snapshot. Mirrors ``scripts/dev_seed_and_serve.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from mygm_api.models import League, LeagueId, VersionId
from mygm_api.schemas import LeagueAnalyticsSnapshotResponse
from mygm_api.security import UserId

if TYPE_CHECKING:
    from mygm_api.store import ApiStore

# Matches apps/web/lib/session.ts (local alpha session) and the homepage demo link.
ALPHA_USER = UserId("local-alpha-user")
DEMO_LEAGUE = LeagueId(UUID("11111111-1111-4111-8111-111111111111"))
DEMO_ORG = UUID("00000000-0000-0000-0000-000000000001")
SNAPSHOT_PATH = Path(__file__).with_name("demo_snapshot.json")


def seed_demo_league(store: ApiStore) -> bool:
    """Inject the demo league + snapshot and grant the alpha user access.

    Returns True if seeding ran, False if the bundled snapshot is missing. Never raises
    for missing data so a deployment without the snapshot still boots.
    """
    if not SNAPSHOT_PATH.exists():
        return False
    store.accept_invite(ALPHA_USER)
    store.leagues[DEMO_LEAGUE] = League(
        id=DEMO_LEAGUE,
        org_id=DEMO_ORG,
        espn_league_id="18254195",
        name="Demo Dynasty League",
        created_by=ALPHA_USER,
    )
    store.memberships[DEMO_LEAGUE] = {ALPHA_USER}
    snapshot = LeagueAnalyticsSnapshotResponse.model_validate_json(
        SNAPSHOT_PATH.read_text(encoding="utf-8"),
    )
    version_id = VersionId(uuid4())
    store.analytics_snapshots[(DEMO_LEAGUE, version_id)] = snapshot
    store.current_analytics_version_by_league[DEMO_LEAGUE] = version_id
    return True
