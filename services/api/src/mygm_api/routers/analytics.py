from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from mygm_api.analytics_fixtures import (
    analytics_repository,
)
from mygm_api.analytics_snapshots import (
    LeagueAnalyticsSnapshot,
    snapshot_analytics_repository,
)
from mygm_api.dependencies import StoreDep, UserDep, parse_league_id, require_league_access
from mygm_api.models import LeagueId
from mygm_api.schemas import (
    AvailableSeasonsResponse,
    DashboardResponse,
    DataHealthResponse,
    FormulaResponse,
    ImportRunListResponse,
    ImportRunResponse,
    LeagueHistoryResponse,
    LeagueNewsResponse,
    ManagerDirectoryResponse,
    ManagerHubResponse,
    ManagerProfileResponse,
    PlayerLeaderboardsResponse,
    RivalryMatrixResponse,
    SeasonHubResponse,
    SnapshotDetailResponse,
    SnapshotHeadToHeadResponse,
    SnapshotRowsResponse,
    WeeklyPointsResponse,
)
from mygm_api.score_models import (
    CURRENT_VERSION_ALIAS,
)
from mygm_api.store import ApiStore

router = APIRouter(tags=["analytics"])


@dataclass(frozen=True, slots=True)
class HeadToHeadQuery:
    season: str
    manager_a: str
    manager_b: str
    version: str


def parse_head_to_head_query(
    season: Annotated[str, Query()],
    manager_a: Annotated[str, Query(alias="managerA")],
    manager_b: Annotated[str, Query(alias="managerB")],
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
) -> HeadToHeadQuery:
    return HeadToHeadQuery(
        season=season,
        manager_a=manager_a,
        manager_b=manager_b,
        version=version,
    )


@router.get("/admin/import-runs", operation_id="list_admin_import_runs")
async def list_admin_import_runs(user: UserDep, api_store: StoreDep) -> ImportRunListResponse:
    if not user.is_admin:
        return ImportRunListResponse(runs=[])
    runs = [
        ImportRunResponse(
            runId=UUID(str(run.id)),
            leagueId=UUID(str(run.league_id)),
            status=run.status,
            step=run.step,
            credentialVersion=run.credential_version,
            warnings=list(run.warnings),
            sourceCounts=analytics_repository.dashboard_counts(),
            errorSummary=None,
            createdAt=run.created_at,
        )
        for run in api_store.import_runs.values()
    ]
    return ImportRunListResponse(runs=runs)


@router.get("/leagues/{league_id}/dashboard", operation_id="get_league_dashboard")
async def get_league_dashboard(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
) -> DashboardResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    return snapshot_analytics_repository.dashboard(current, league_id)


@router.get(
    "/leagues/{league_id}/history",
    operation_id="get_league_history",
)
async def get_league_history(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
) -> LeagueHistoryResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    return snapshot_analytics_repository.history(current)


@router.get(
    "/leagues/{league_id}/rivalries",
    operation_id="get_league_rivalries",
)
async def get_league_rivalries(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
) -> RivalryMatrixResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    return snapshot_analytics_repository.rivalries(current)


@router.get(
    "/leagues/{league_id}/managers",
    operation_id="list_league_managers",
)
async def list_league_managers(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
) -> ManagerDirectoryResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    return snapshot_analytics_repository.managers_directory(current)


@router.get(
    "/leagues/{league_id}/managers/{manager_key}",
    operation_id="get_league_manager_hub",
)
async def get_league_manager_hub(
    league_id: Annotated[UUID, Path()],
    manager_key: Annotated[str, Path()],
    user: UserDep,
    api_store: StoreDep,
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
) -> ManagerHubResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    try:
        return snapshot_analytics_repository.manager_hub(current, manager_key)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="manager not found") from exc


@router.get(
    "/leagues/{league_id}/seasons",
    operation_id="list_league_analytics_seasons",
)
async def list_league_analytics_seasons(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
) -> AvailableSeasonsResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    return snapshot_analytics_repository.available_seasons(current)


@router.get(
    "/leagues/{league_id}/seasons/{season_year}/hub",
    operation_id="get_league_season_hub",
)
async def get_league_season_hub(
    league_id: Annotated[UUID, Path()],
    season_year: Annotated[int, Path()],
    user: UserDep,
    api_store: StoreDep,
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
) -> SeasonHubResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    try:
        return snapshot_analytics_repository.season_hub(current, season_year)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="season not found") from exc


@router.get("/leagues/{league_id}/seasons/{season_year}", operation_id="get_league_season")
async def get_league_season(
    league_id: Annotated[UUID, Path()],
    season_year: Annotated[int, Path()],
    user: UserDep,
    api_store: StoreDep,
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
    formula: Annotated[str | None, Query()] = None,
) -> SnapshotRowsResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    return snapshot_analytics_repository.season(current, season_year, formula)


@router.get(
    "/leagues/{league_id}/leaderboard",
    operation_id="list_league_leaderboard",
)
async def list_league_leaderboard(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
    scope: Annotated[str, Query()] = "all_time",
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
    formula: Annotated[str | None, Query()] = None,
) -> SnapshotRowsResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    return snapshot_analytics_repository.leaderboard(current, scope, formula)


@router.get(
    "/leagues/{league_id}/gms",
    operation_id="list_gm_ratings",
)
async def list_gm_ratings(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
    scope: Annotated[str, Query()] = "all_time",
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
    formula: Annotated[str | None, Query()] = None,
) -> SnapshotRowsResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    return snapshot_analytics_repository.leaderboard(current, scope, formula)


@router.get(
    "/leagues/{league_id}/gms/{manager_id}",
    operation_id="get_manager_report",
)
async def get_manager_report(
    league_id: Annotated[UUID, Path()],
    manager_id: Annotated[str, Path()],
    user: UserDep,
    api_store: StoreDep,
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
    formula: Annotated[str | None, Query()] = None,
) -> ManagerProfileResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    try:
        return snapshot_analytics_repository.manager(current, manager_id, formula)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="manager not found") from exc


@router.get(
    "/leagues/{league_id}/trades",
    operation_id="list_trade_grades",
)
async def list_trade_grades(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
) -> SnapshotRowsResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    return snapshot_analytics_repository.trades(current)


@router.get(
    "/leagues/{league_id}/trades/{trade_id}",
    operation_id="get_trade_grade_detail",
)
async def get_trade_grade_detail(
    league_id: Annotated[UUID, Path()],
    trade_id: Annotated[str, Path()],
    user: UserDep,
    api_store: StoreDep,
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
) -> SnapshotDetailResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    detail = snapshot_analytics_repository.trade_detail(current, trade_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="trade not found")
    return detail


@router.get(
    "/leagues/{league_id}/waivers",
    operation_id="list_waiver_grades",
)
async def list_waiver_grades(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
) -> SnapshotRowsResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    return snapshot_analytics_repository.waivers(current)


@router.get(
    "/leagues/{league_id}/waivers/{waiver_id}",
    operation_id="get_waiver_grade_detail",
)
async def get_waiver_grade_detail(
    league_id: Annotated[UUID, Path()],
    waiver_id: Annotated[str, Path()],
    user: UserDep,
    api_store: StoreDep,
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
) -> SnapshotDetailResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    detail = snapshot_analytics_repository.waiver_detail(current, waiver_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="waiver not found")
    return detail


@router.get(
    "/leagues/{league_id}/records",
    operation_id="list_league_records",
)
async def list_league_records(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
) -> SnapshotRowsResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    return snapshot_analytics_repository.records(current)


@router.get(
    "/leagues/{league_id}/formula",
    operation_id="get_league_formula",
)
async def get_league_formula(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
) -> FormulaResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    formula = snapshot_analytics_repository.formula(current)
    return FormulaResponse(
        scoreModels=analytics_repository.score_models(),
        formulaVersion=formula.formula_version,
        provenance=formula.provenance,
        caveat="Retrospective value captured from completed seasons, not a projection.",
        weights=snapshot_analytics_repository.formula_weights(current),
        componentLabels=snapshot_analytics_repository.component_labels(current),
        availableFormulas=snapshot_analytics_repository.available_formulas(current),
    )


@router.get(
    "/leagues/{league_id}/news",
    operation_id="get_league_news",
)
async def get_league_news(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
) -> LeagueNewsResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    return snapshot_analytics_repository.news(current)


@router.get(
    "/leagues/{league_id}/data-health",
    operation_id="get_league_data_health",
)
async def get_league_data_health(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
) -> DataHealthResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    health = snapshot_analytics_repository.data_health(current)
    return DataHealthResponse(
        modelName="data_health",
        status=health.status,
        careerExclusion="; ".join(health.caveats),
        faabContext="; ".join(health.withheld_scores),
        careerExcludedSeasons=health.career_excluded_seasons,
        warnings=health.warnings,
        withheldScores=health.withheld_scores,
        caveats=health.caveats,
        ungradedExecutedAccepts=_ungraded_executed_accepts(health.source_counts),
    )


def _ungraded_executed_accepts(source_counts: dict[str, int]) -> int | None:
    """Source-backed ungraded executed accepts from a snapshot's own counts.

    Prefers the explicit count, otherwise derives it from executed minus graded
    rows. Returns ``None`` when the snapshot does not carry the inputs, so the
    surface shows a pending state instead of a fabricated number.
    """
    direct = source_counts.get("ungradedExecutedAccepts")
    if direct is not None:
        return direct
    executed = source_counts.get("executedAcceptedTrades")
    graded = source_counts.get("gradedTradeRows")
    if executed is None or graded is None:
        return None
    return max(executed - graded, 0)


@router.get(
    "/leagues/{league_id}/head-to-head",
    operation_id="get_league_head_to_head",
)
async def get_league_head_to_head(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
    query: Annotated[HeadToHeadQuery, Depends(parse_head_to_head_query)],
) -> SnapshotHeadToHeadResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, query.version)
    return snapshot_analytics_repository.head_to_head(
        current,
        query.season,
        query.manager_a,
        query.manager_b,
    )


@router.get(
    "/leagues/{league_id}/players/leaderboards",
    operation_id="get_league_player_leaderboards",
)
async def get_league_player_leaderboards(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
    version: Annotated[str, Query()] = CURRENT_VERSION_ALIAS,
) -> PlayerLeaderboardsResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    current = require_current_snapshot(api_store, parsed, version)
    return snapshot_analytics_repository.player_leaderboards(current)


@router.get(
    "/leagues/{league_id}/players/{player_id}/weekly-points",
    operation_id="get_player_weekly_points",
)
async def get_player_weekly_points(
    league_id: Annotated[UUID, Path()],
    player_id: Annotated[str, Path()],
    user: UserDep,
    api_store: StoreDep,
    season: Annotated[int, Query()] = 2025,
) -> WeeklyPointsResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    return WeeklyPointsResponse(playerId=player_id, season=season, weeklyPoints=[])


def require_current_snapshot(
    api_store: ApiStore,
    league_id: LeagueId,
    version: str,
) -> LeagueAnalyticsSnapshot:
    current = snapshot_analytics_repository.get(api_store, league_id, version)
    if current is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="analytics snapshot required")
    return current
