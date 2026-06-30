from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from mygm_api.models import ClaimStatus, CredentialStatus, RunStatus

type SnapshotJsonValue = (
    None | bool | int | float | str | list["SnapshotJsonValue"] | dict[str, "SnapshotJsonValue"]
)
type SnapshotJsonObject = dict[str, SnapshotJsonValue]


class ApiModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        populate_by_name=True,
        extra="forbid",
    )


class SnapshotApiModel(ApiModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        populate_by_name=True,
        extra="allow",
    )


class InviteAcceptRequest(ApiModel):
    email: str
    invite_code: str = Field(alias="inviteCode", min_length=1)


class ProfileResponse(ApiModel):
    user_id: str = Field(alias="userId")
    email: str
    alpha_access: bool = Field(alias="alphaAccess")
    organization_ids: list[UUID] = Field(alias="organizationIds")
    league_ids: list[UUID] = Field(alias="leagueIds")
    internal_admin: bool = Field(alias="internalAdmin")


class InviteAcceptResponse(ApiModel):
    alpha_access: bool = Field(alias="alphaAccess")
    organization_id: UUID = Field(alias="organizationId")


class LeagueCreateRequest(ApiModel):
    espn_league_id: str = Field(alias="espnLeagueId", min_length=1)
    name: str = Field(min_length=1)


class LeagueResponse(ApiModel):
    league_id: UUID = Field(alias="leagueId")
    organization_id: UUID = Field(alias="organizationId")
    espn_league_id: str = Field(alias="espnLeagueId")
    name: str
    current_version_id: UUID | None = Field(alias="currentVersionId")


class LeagueListResponse(ApiModel):
    leagues: list[LeagueResponse]


class CredentialStoreRequest(ApiModel):
    league_id: UUID = Field(alias="leagueId")
    swid: str = Field(alias="SWID", min_length=1)
    espn_s2: str = Field(alias="espn_s2", min_length=1)
    consent_version: str = Field(alias="consentVersion", min_length=1)
    start_year: int = Field(alias="startYear", ge=2000)
    end_year: int = Field(alias="endYear", ge=2000)


class CredentialResponse(ApiModel):
    credential_version: int = Field(alias="credentialVersion")
    key_id: str = Field(alias="keyId")
    status: CredentialStatus
    consent_version: str = Field(alias="consentVersion")
    expires_at: datetime = Field(alias="expiresAt")
    rotated_at: datetime | None = Field(alias="rotatedAt")
    last_validated_at: datetime | None = Field(alias="lastValidatedAt")


class CredentialValidateResponse(ApiModel):
    status: str
    league_name: str = Field(alias="leagueName")
    seasons: list[int]


class CredentialRevokeResponse(ApiModel):
    status: CredentialStatus


class ManagerClaimCreateRequest(ApiModel):
    league_id: UUID = Field(alias="leagueId")
    espn_team_id: str = Field(alias="espnTeamId", min_length=1)


class ManagerClaimPatchRequest(ApiModel):
    status: ClaimStatus


class ManagerClaimResponse(ApiModel):
    claim_id: UUID = Field(alias="claimId")
    league_id: UUID = Field(alias="leagueId")
    espn_team_id: str = Field(alias="espnTeamId")
    status: ClaimStatus


class ImportRunCreateRequest(ApiModel):
    start_year: int = Field(alias="startYear", ge=2000)
    end_year: int = Field(alias="endYear", ge=2000)
    include_activity: bool = Field(alias="includeActivity")
    force_refresh: bool = Field(alias="forceRefresh")


class ImportRunResponse(ApiModel):
    run_id: UUID = Field(alias="runId")
    league_id: UUID = Field(alias="leagueId")
    status: RunStatus
    step: str
    credential_version: int = Field(alias="credentialVersion")
    warnings: list[str]
    source_counts: dict[str, int] = Field(alias="sourceCounts")
    error_summary: str | None = Field(alias="errorSummary")
    created_at: datetime = Field(alias="createdAt")


class ReprocessRunResponse(ApiModel):
    run_id: UUID = Field(alias="runId")
    league_id: UUID = Field(alias="leagueId")
    status: RunStatus
    step: str
    source_counts: dict[str, int] = Field(alias="sourceCounts")
    caveats: list[str]
    warnings: list[str]
    error_summary: str | None = Field(alias="errorSummary")
    created_at: datetime = Field(alias="createdAt")


class ImportRunListResponse(ApiModel):
    runs: list[ImportRunResponse]


class ArtifactManifestResponse(ApiModel):
    raw_bucket: str = Field(alias="rawBucket")
    raw_prefix: str = Field(alias="rawPrefix")
    derived_bucket: str = Field(alias="derivedBucket")
    derived_prefix: str = Field(alias="derivedPrefix")


class ReprocessRunCreateRequest(ApiModel):
    source_import_run_id: UUID = Field(alias="sourceImportRunId")
    targets: list[str]
    formula_version: str = Field(alias="formulaVersion")


class VersionPublishResponse(ApiModel):
    version_id: UUID = Field(alias="versionId")
    alias: str
    published: bool


class DashboardResponse(ApiModel):
    league_id: UUID = Field(alias="leagueId")
    version: str
    payload_version: str = Field(alias="payloadVersion")
    product_label: str = Field(alias="productLabel")
    import_status: str | RunStatus = Field(alias="importStatus")
    composite_score: float = Field(alias="compositeScore")
    source_counts: dict[str, int] = Field(alias="sourceCounts")
    career_excluded_seasons: list[int] = Field(alias="careerExcludedSeasons")
    leaderboard: list[SnapshotJsonObject] = Field(default_factory=list)


class ManagerReportResponse(ApiModel):
    manager_id: UUID = Field(alias="managerId")
    version: str
    product_label: str = Field(alias="productLabel")
    composite_score: float = Field(alias="compositeScore")
    confidence: str
    source_coverage: str = Field(alias="sourceCoverage")
    career_excluded_seasons: list[int] = Field(alias="careerExcludedSeasons")


class AnalyticsRowResponse(ApiModel):
    label: str
    value: float
    counts: dict[str, int]
    caveats: list[str]


class AnalyticsCollectionResponse(ApiModel):
    model_name: str = Field(alias="modelName")
    model_version: str = Field(alias="modelVersion")
    confidence: str
    source_coverage: str = Field(alias="sourceCoverage")
    rows: list[AnalyticsRowResponse]


class FormulaResponse(ApiModel):
    score_models: list[str] = Field(alias="scoreModels")
    formula_version: str = Field(alias="formulaVersion")
    provenance: str
    caveat: str
    weights: dict[str, float] = Field(default_factory=dict)
    component_labels: dict[str, str] = Field(default_factory=dict, alias="componentLabels")
    available_formulas: list[SnapshotJsonObject] = Field(
        default_factory=list, alias="availableFormulas",
    )


class LeagueNewsResponse(ApiModel):
    season: int
    items: list[SnapshotJsonObject] = Field(default_factory=list)
    team_strength: list[SnapshotJsonObject] = Field(
        default_factory=list, alias="teamStrength",
    )
    waiver_suggestions: list[SnapshotJsonObject] = Field(
        default_factory=list, alias="waiverSuggestions",
    )


class DataHealthResponse(ApiModel):
    model_name: str = Field(alias="modelName")
    status: str
    career_exclusion: str = Field(alias="careerExclusion")
    faab_context: str = Field(alias="faabContext")
    career_excluded_seasons: list[int] = Field(alias="careerExcludedSeasons")
    warnings: list[str]
    withheld_scores: list[str] = Field(alias="withheldScores")
    caveats: list[str]
    ungraded_executed_accepts: int | None = Field(
        default=None, alias="ungradedExecutedAccepts",
    )


class SnapshotMetaResponse(SnapshotApiModel):
    snapshot_version: str = Field(alias="snapshotVersion", min_length=1)
    source: str
    generated_at: str = Field(alias="generatedAt")
    product_label: str = Field(alias="productLabel")
    formula_version: str = Field(alias="formulaVersion")
    import_status: str = Field(alias="importStatus")


class SnapshotLeagueResponse(SnapshotApiModel):
    league_id: str = Field(alias="leagueId")
    name: str
    platform: str


class SnapshotSeasonResponse(SnapshotApiModel):
    season: int
    final_week: int = Field(alias="finalWeek", ge=0)
    is_partial: bool = Field(alias="isPartial")


class SnapshotManagerTeamAliasResponse(SnapshotApiModel):
    season: int
    team_id: int = Field(alias="teamId")
    team_name: str = Field(alias="teamName")


class SnapshotManagerResponse(SnapshotApiModel):
    manager_key: str = Field(alias="managerKey", min_length=1)
    display_name: str = Field(alias="displayName")
    team_aliases: list[SnapshotManagerTeamAliasResponse] = Field(
        default_factory=list,
        alias="aliases",
    )
    owner_id: str | None = Field(default=None, alias="ownerId")
    score_eligible: bool = Field(alias="scoreEligible")
    caveats: list[str]


class SnapshotLeaderboardRowResponse(SnapshotApiModel):
    rank: int
    manager_key: str = Field(alias="managerKey", min_length=1)
    score: float
    confidence: str
    season: int | None = None
    components: dict[str, float] = Field(default_factory=dict)
    caveats: list[str] = Field(default_factory=list)


class SnapshotLeaderboardsResponse(SnapshotApiModel):
    all_time: list[SnapshotLeaderboardRowResponse] = Field(alias="allTime")
    by_season: list[SnapshotLeaderboardRowResponse] = Field(alias="bySeason")


class SnapshotTradeEventResponse(SnapshotApiModel):
    trade_id: str = Field(alias="tradeId", min_length=1)
    season: int
    manager_keys: list[str] = Field(alias="managerKeys", min_length=2)
    score_eligible: bool = Field(alias="scoreEligible")
    caveats: list[str]


class SnapshotTradeCollectionResponse(SnapshotApiModel):
    items: list[SnapshotTradeEventResponse]


class SnapshotWaiverMoveResponse(SnapshotApiModel):
    move_id: str = Field(alias="moveId", min_length=1)
    season: int
    manager_key: str = Field(alias="managerKey", min_length=1)
    transaction_type: str = Field(default="WAIVER", alias="transactionType")
    score_eligible: bool = Field(alias="scoreEligible")
    caveats: list[str]


class SnapshotWaiverCollectionResponse(SnapshotApiModel):
    items: list[SnapshotWaiverMoveResponse]


class SnapshotRecordResponse(SnapshotApiModel):
    record_id: str = Field(alias="recordId", min_length=1)
    category: str
    label: str
    value: float
    manager_key: str | None = Field(alias="managerKey")


class SnapshotRecordCollectionResponse(SnapshotApiModel):
    items: list[SnapshotRecordResponse]


class SnapshotHeadToHeadPairResponse(SnapshotApiModel):
    pair_id: str = Field(alias="pairId", min_length=1)
    manager_a_key: str = Field(alias="managerAKey", min_length=1)
    manager_b_key: str = Field(alias="managerBKey", min_length=1)
    matchups: list[dict[str, str | int | float | bool]]
    caveats: list[str]


class SnapshotHeadToHeadResponse(SnapshotApiModel):
    pairs: list[SnapshotHeadToHeadPairResponse]


class SnapshotDataHealthResponse(SnapshotApiModel):
    status: str
    source_counts: dict[str, int] = Field(default_factory=dict, alias="sourceCounts")
    career_excluded_seasons: list[int] = Field(default_factory=list, alias="careerExcludedSeasons")
    caveats: list[str]
    warnings: list[str]
    withheld_scores: list[str] = Field(alias="withheldScores")


class SnapshotFormulaResponse(SnapshotApiModel):
    formula_version: str = Field(alias="formulaVersion")
    provenance: str
    weights: dict[str, float]


class LeagueAnalyticsSnapshotResponse(SnapshotApiModel):
    meta: SnapshotMetaResponse
    league: SnapshotLeagueResponse
    seasons: list[SnapshotSeasonResponse]
    managers: list[SnapshotManagerResponse]
    leaderboards: SnapshotLeaderboardsResponse
    trades: SnapshotTradeCollectionResponse
    waivers: SnapshotWaiverCollectionResponse
    records: SnapshotRecordCollectionResponse
    head_to_head: SnapshotHeadToHeadResponse = Field(alias="headToHead")
    data_health: SnapshotDataHealthResponse = Field(alias="dataHealth")
    formula: SnapshotFormulaResponse


class AvailableSeasonsResponse(ApiModel):
    seasons: list[int]


class SnapshotRowsResponse(ApiModel):
    model_name: str = Field(alias="modelName")
    model_version: str = Field(alias="modelVersion")
    rows: list[SnapshotJsonObject]
    # Optional per-section extras (e.g. waivers carry per-season award cards keyed by season).
    waiver_superlatives: dict[str, SnapshotJsonObject] = Field(
        default_factory=dict,
        alias="waiverSuperlatives",
    )


class SnapshotDetailResponse(ApiModel):
    item: SnapshotJsonObject


class HistorySeasonResponse(ApiModel):
    season: int
    is_partial: bool = Field(alias="isPartial")
    final_week: int | None = Field(default=None, alias="finalWeek")
    transaction_count: int | None = Field(default=None, alias="transactionCount")
    champion: SnapshotJsonObject | None = None
    runner_up: SnapshotJsonObject | None = Field(default=None, alias="runnerUp")
    headline: str
    superlatives: list[SnapshotJsonObject] = Field(default_factory=list)


class HistoryChampionResponse(ApiModel):
    manager_key: str = Field(alias="managerKey")
    display_name: str = Field(alias="displayName")
    titles: int


class LeagueHistoryResponse(ApiModel):
    span: str
    season_count: int = Field(alias="seasonCount")
    seasons: list[HistorySeasonResponse]
    champions: list[HistoryChampionResponse]


class ManagerDirectoryEntry(ApiModel):
    manager_key: str = Field(alias="managerKey")
    display_name: str = Field(alias="displayName")
    latest_team_name: str | None = Field(default=None, alias="latestTeamName")
    seasons_played: int | None = Field(default=None, alias="seasonsPlayed")
    titles: int | None = None
    win_pct: float | None = Field(default=None, alias="winPct")
    best_finish: int | None = Field(default=None, alias="bestFinish")
    career_rating: float | None = Field(default=None, alias="careerRating")
    logo: SnapshotJsonObject | None = None
    signature_player: SnapshotJsonObject | None = Field(default=None, alias="signaturePlayer")


class ManagerDirectoryResponse(ApiModel):
    managers: list[ManagerDirectoryEntry]


class RivalryMatrixResponse(ApiModel):
    managers: list[SnapshotJsonObject] = Field(default_factory=list)
    edges: list[SnapshotJsonObject] = Field(default_factory=list)
    summaries: list[SnapshotJsonObject] = Field(default_factory=list)


class PlayerLeaderboardsResponse(ApiModel):
    top_weeks: list[SnapshotJsonObject] = Field(default_factory=list, alias="topWeeks")
    top_seasons: list[SnapshotJsonObject] = Field(default_factory=list, alias="topSeasons")
    lineup_efficiency: list[SnapshotJsonObject] = Field(
        default_factory=list,
        alias="lineupEfficiency",
    )
    player_directory: dict[str, SnapshotJsonObject] = Field(
        default_factory=dict,
        alias="playerDirectory",
    )


class SeasonHubResponse(ApiModel):
    season: int
    is_partial: bool = Field(alias="isPartial")
    final_week: int | None = Field(default=None, alias="finalWeek")
    transaction_count: int | None = Field(default=None, alias="transactionCount")
    playoff_team_count: int | None = Field(default=None, alias="playoffTeamCount")
    champion: SnapshotJsonObject | None = None
    runner_up: SnapshotJsonObject | None = Field(default=None, alias="runnerUp")
    final_standings: list[SnapshotJsonObject] = Field(default_factory=list, alias="finalStandings")
    draft_recap: SnapshotJsonObject = Field(default_factory=dict, alias="draftRecap")
    superlatives: list[SnapshotJsonObject] = Field(default_factory=list)
    ratings: list[SnapshotJsonObject] = Field(default_factory=list)
    review: list[str] = Field(default_factory=list)


class ManagerHubResponse(ApiModel):
    manager_key: str = Field(alias="managerKey")
    display_name: str = Field(alias="displayName")
    team_aliases: list[SnapshotJsonObject] = Field(default_factory=list, alias="teamAliases")
    score_eligible: bool = Field(alias="scoreEligible")
    caveats: list[str] = Field(default_factory=list)
    career_rating: float | None = Field(default=None, alias="careerRating")
    rating_components: dict[str, dict[str, str | float]] = Field(
        default_factory=dict,
        alias="ratingComponents",
    )
    career: SnapshotJsonObject = Field(default_factory=dict)
    value: SnapshotJsonObject = Field(default_factory=dict)
    rivalry: SnapshotJsonObject = Field(default_factory=dict)
    archetype: SnapshotJsonObject = Field(default_factory=dict)
    draft_card: SnapshotJsonObject = Field(default_factory=dict, alias="draftCard")
    roster_history: SnapshotJsonObject = Field(default_factory=dict, alias="rosterHistory")


class ManagerProfileResponse(ApiModel):
    manager_key: str = Field(alias="managerKey")
    display_name: str = Field(alias="displayName")
    team_aliases: list[SnapshotManagerTeamAliasResponse] = Field(alias="teamAliases")
    score_eligible: bool = Field(alias="scoreEligible")
    caveats: list[str]
    composite_score: float | None = Field(default=None, alias="compositeScore")
    confidence: str | None = None
    component_breakdown: dict[str, dict[str, str | float]] = Field(
        default_factory=dict, alias="componentBreakdown",
    )
    archetype: SnapshotJsonObject = Field(default_factory=dict)


class WeeklyPointsResponse(ApiModel):
    player_id: str = Field(alias="playerId")
    season: int
    weekly_points: list[float] = Field(alias="weeklyPoints")


class ShareLinkListResponse(ApiModel):
    share_links: list["ShareLinkResponse"] = Field(alias="shareLinks")


class ShareLinkCreateRequest(ApiModel):
    manager_id: UUID = Field(alias="managerId")
    version_id: UUID = Field(alias="versionId")
    expires_at: datetime | None = Field(alias="expiresAt")


class ShareLinkResponse(ApiModel):
    share_link_id: UUID = Field(alias="shareLinkId")
    share_slug: str = Field(alias="shareSlug")
    league_id: UUID = Field(alias="leagueId")
    version_id: UUID = Field(alias="versionId")
    revoked: bool


class SharePayloadResponse(ApiModel):
    share_slug: str = Field(alias="shareSlug")
    title: str
    privacy: str
    payload_version: str = Field(alias="payloadVersion")
    product_label: str = Field(alias="productLabel")
    composite_score: float = Field(alias="compositeScore")
    canonical_graded_trade_events: int = Field(alias="canonicalGradedTradeEvents")
    ungraded_executed_accepts: int = Field(alias="ungradedExecutedAccepts")
    faab_context: str = Field(alias="faabContext")
    career_excluded_seasons: list[int] = Field(alias="careerExcludedSeasons")
