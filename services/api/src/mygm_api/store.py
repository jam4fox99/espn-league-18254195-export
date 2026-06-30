from dataclasses import dataclass, field, replace
from uuid import UUID, uuid4

from mygm_api.models import (
    ClaimStatus,
    EncryptedCredential,
    ImportRun,
    League,
    LeagueId,
    ManagerClaim,
    RunId,
    RunStatus,
    ShareLink,
    VersionId,
    new_league_id,
    new_run_id,
)
from mygm_api.schemas import LeagueAnalyticsSnapshotResponse
from mygm_api.security import UserId


@dataclass(slots=True)
class ApiStore:
    accepted_invites: set[UserId] = field(default_factory=set)
    leagues: dict[LeagueId, League] = field(default_factory=dict)
    memberships: dict[LeagueId, set[UserId]] = field(default_factory=dict)
    credentials: dict[LeagueId, EncryptedCredential] = field(default_factory=dict)
    claims: dict[UUID, ManagerClaim] = field(default_factory=dict)
    import_runs: dict[RunId, ImportRun] = field(default_factory=dict)
    import_idempotency: dict[tuple[LeagueId, str, UserId], RunId] = field(default_factory=dict)
    reprocess_runs: dict[RunId, ImportRun] = field(default_factory=dict)
    analytics_snapshots: dict[
        tuple[LeagueId, VersionId],
        LeagueAnalyticsSnapshotResponse,
    ] = field(default_factory=dict)
    current_analytics_version_by_league: dict[LeagueId, VersionId] = field(default_factory=dict)
    active_analytics_recompute_by_league: dict[LeagueId, RunId] = field(default_factory=dict)
    published_versions: set[VersionId] = field(default_factory=set)
    share_links: dict[UUID, ShareLink] = field(default_factory=dict)
    rate_limit_hits: dict[tuple[UserId, str], int] = field(default_factory=dict)

    def accept_invite(self, user_id: UserId) -> None:
        self.accepted_invites.add(user_id)

    def is_invited(self, user_id: UserId) -> bool:
        return user_id in self.accepted_invites

    def create_league(self, user_id: UserId, espn_league_id: str, name: str) -> League:
        league = League(
            id=new_league_id(),
            org_id=uuid4(),
            espn_league_id=espn_league_id,
            name=name,
            created_by=user_id,
        )
        self.leagues[league.id] = league
        self.memberships[league.id] = {user_id}
        return league

    def has_league_access(self, user_id: UserId, league_id: LeagueId) -> bool:
        return user_id in self.memberships.get(league_id, set())

    def next_credential_version(self, league_id: LeagueId) -> int:
        credential = self.credentials.get(league_id)
        if credential is None:
            return 1
        return credential.credential_version + 1

    def store_credential(self, credential: EncryptedCredential) -> None:
        self.credentials[credential.league_id] = credential

    def create_claim(self, user_id: UserId, league_id: LeagueId, espn_team_id: str) -> ManagerClaim:
        claim = ManagerClaim(
            id=uuid4(),
            league_id=league_id,
            espn_team_id=espn_team_id,
            status=ClaimStatus.PENDING,
            requested_by=user_id,
        )
        self.claims[claim.id] = claim
        return claim

    def enqueue_import(
        self,
        user_id: UserId,
        league_id: LeagueId,
        idempotency_key: str | None,
    ) -> ImportRun:
        if idempotency_key is not None:
            key = (league_id, idempotency_key, user_id)
            existing = self.import_idempotency.get(key)
            if existing is not None:
                return self.import_runs[existing]
        credential = self.credentials[league_id]
        run = ImportRun(
            id=new_run_id(),
            league_id=league_id,
            requested_by=user_id,
            status=RunStatus.QUEUED,
            credential_version=credential.credential_version,
            idempotency_key=idempotency_key,
        )
        self.import_runs[run.id] = run
        if idempotency_key is not None:
            self.import_idempotency[(league_id, idempotency_key, user_id)] = run.id
        return run

    def cancel_import(self, run_id: RunId) -> ImportRun:
        run = self.import_runs[run_id]
        updated = replace(run, status=RunStatus.CANCEL_REQUESTED)
        self.import_runs[run_id] = updated
        return updated

    def retry_import(self, run_id: RunId) -> ImportRun:
        run = self.import_runs[run_id]
        updated = replace(run, status=RunStatus.QUEUED)
        self.import_runs[run_id] = updated
        return updated

    def enqueue_reprocess(self, user_id: UserId, league_id: LeagueId) -> ImportRun | None:
        if league_id in self.active_analytics_recompute_by_league:
            return None
        run = ImportRun(
            id=new_run_id(),
            league_id=league_id,
            requested_by=user_id,
            status=RunStatus.QUEUED,
            credential_version=self.credentials[league_id].credential_version,
            idempotency_key=None,
            step="derive_snapshot",
        )
        self.reprocess_runs[run.id] = run
        self.active_analytics_recompute_by_league[league_id] = run.id
        return run

    def current_snapshot_source_counts(self, league_id: LeagueId) -> dict[str, int] | None:
        version_id = self.current_analytics_version_by_league.get(league_id)
        if version_id is None:
            return None
        snapshot = self.analytics_snapshots.get((league_id, version_id))
        if snapshot is None:
            return None
        return dict(snapshot.data_health.source_counts)

    def current_snapshot_caveats(self, league_id: LeagueId) -> list[str] | None:
        version_id = self.current_analytics_version_by_league.get(league_id)
        if version_id is None:
            return None
        snapshot = self.analytics_snapshots.get((league_id, version_id))
        if snapshot is None:
            return None
        return list(snapshot.data_health.caveats)

    def create_share_link(self, league_id: LeagueId, version_id: VersionId) -> ShareLink:
        share_id = uuid4()
        share = ShareLink(
            id=share_id,
            league_id=league_id,
            version_id=version_id,
            slug=share_id.hex[:16],
            revoked=False,
        )
        self.share_links[share.id] = share
        return share

    def revoke_share_link(self, share_link_id: UUID) -> ShareLink:
        share = self.share_links[share_link_id]
        revoked = replace(share, revoked=True)
        self.share_links[share_link_id] = revoked
        return revoked

    def allow_rate_limited_action(self, user_id: UserId, action: str, limit: int) -> bool:
        key = (user_id, action)
        hits = self.rate_limit_hits.get(key, 0) + 1
        self.rate_limit_hits[key] = hits
        return hits <= limit
