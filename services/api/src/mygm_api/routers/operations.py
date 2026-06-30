from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Path, status

from mygm_api.analytics_fixtures import analytics_repository
from mygm_api.config import get_settings
from mygm_api.crypto import CredentialEncryptor, CredentialSecret
from mygm_api.dependencies import (
    StoreDep,
    UserDep,
    parse_league_id,
    parse_run_id,
    require_league_access,
)
from mygm_api.models import EncryptedCredential, ImportRun, VersionId
from mygm_api.rate_limit import enforce_rate_limit
from mygm_api.schemas import (
    ArtifactManifestResponse,
    CredentialResponse,
    CredentialStoreRequest,
    CredentialValidateResponse,
    ImportRunCreateRequest,
    ImportRunResponse,
    ReprocessRunCreateRequest,
    ReprocessRunResponse,
    VersionPublishResponse,
)
from mygm_api.score_models import CURRENT_VERSION_ALIAS
from mygm_api.storage_paths import contract_storage_paths
from mygm_api.store import ApiStore

router = APIRouter(tags=["operations"])
SUPPORTED_REPROCESS_TARGETS = {"analyticsSnapshot", "analytics_snapshot"}
SUPPORTED_REPROCESS_FORMULA_VERSION = "mygm-retrospective-v1"


@router.post(
    "/leagues/{league_id}/credentials",
    operation_id="store_league_credentials",
)
async def store_league_credentials(
    league_id: Annotated[UUID, Path()],
    payload: CredentialStoreRequest,
    user: UserDep,
    api_store: StoreDep,
) -> CredentialResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    enforce_rate_limit(user, api_store, "store-credentials")
    if payload.league_id != league_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="league id mismatch")
    settings = get_settings()
    version = api_store.next_credential_version(parsed)
    credential = CredentialEncryptor(
        key_id=settings.credential_key_id,
        encoded_key=settings.credential_key,
    ).encrypt(
        league_id=parsed,
        credential_version=version,
        consent_version=payload.consent_version,
        created_by=user.user_id,
        secret=CredentialSecret(swid=payload.swid, espn_s2=payload.espn_s2),
    )
    api_store.store_credential(credential)
    return to_credential_response(credential)


@router.post(
    "/leagues/{league_id}/credentials/validate",
    operation_id="validate_league_credentials",
)
async def validate_league_credentials(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
) -> CredentialValidateResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    league = api_store.leagues[parsed]
    return CredentialValidateResponse(status="valid", leagueName=league.name, seasons=[2020, 2025])


@router.post(
    "/leagues/{league_id}/import-runs",
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="create_import_run",
)
async def create_import_run(
    league_id: Annotated[UUID, Path()],
    payload: ImportRunCreateRequest,
    user: UserDep,
    api_store: StoreDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ImportRunResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    enforce_rate_limit(user, api_store, "create-import-run")
    if payload.end_year < payload.start_year:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="endYear must be >= startYear",
        )
    if parsed not in api_store.credentials:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="credentials required")
    run = api_store.enqueue_import(user.user_id, parsed, idempotency_key)
    return to_run_response(run)


@router.get(
    "/import-runs/{run_id}",
    operation_id="get_import_run",
)
async def get_import_run(
    run_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
) -> ImportRunResponse:
    parsed = parse_run_id(run_id)
    run = api_store.import_runs[parsed]
    require_league_access(user, api_store, run.league_id)
    return to_run_response(run)


@router.get(
    "/import-runs/{run_id}/artifacts",
    operation_id="get_import_run_artifacts",
)
async def get_import_run_artifacts(
    run_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
) -> ArtifactManifestResponse:
    parsed = parse_run_id(run_id)
    run = api_store.import_runs[parsed]
    require_league_access(user, api_store, run.league_id)
    league = api_store.leagues[run.league_id]
    paths = contract_storage_paths(
        organization_id=str(league.org_id),
        league_id=str(league.id),
        run_id=str(run.id),
        version_id=str(UUID(int=2)),
        share_slug="example",
    )
    return ArtifactManifestResponse(
        rawBucket=paths.raw_bucket,
        rawPrefix=paths.raw_prefix,
        derivedBucket=paths.derived_bucket,
        derivedPrefix=paths.derived_prefix,
    )


@router.post(
    "/import-runs/{run_id}/cancel",
    operation_id="cancel_import_run",
)
async def cancel_import_run(
    run_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
) -> ImportRunResponse:
    parsed = parse_run_id(run_id)
    run = api_store.import_runs[parsed]
    require_league_access(user, api_store, run.league_id)
    return to_run_response(api_store.cancel_import(parsed))


@router.post(
    "/import-runs/{run_id}/retry",
    operation_id="retry_import_run",
)
async def retry_import_run(
    run_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
) -> ImportRunResponse:
    parsed = parse_run_id(run_id)
    run = api_store.import_runs[parsed]
    require_league_access(user, api_store, run.league_id)
    return to_run_response(api_store.retry_import(parsed))


@router.post(
    "/leagues/{league_id}/reprocess-runs",
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="create_reprocess_run",
)
async def create_reprocess_run(
    league_id: Annotated[UUID, Path()],
    payload: ReprocessRunCreateRequest,
    user: UserDep,
    api_store: StoreDep,
) -> ReprocessRunResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    if len(payload.targets) != 1 or payload.targets[0] not in SUPPORTED_REPROCESS_TARGETS:
        raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, detail="unsupported reprocess target")
    if payload.formula_version != SUPPORTED_REPROCESS_FORMULA_VERSION:
        raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, detail="unsupported formula version")
    source_run = api_store.import_runs.get(parse_run_id(payload.source_import_run_id))
    if source_run is None or source_run.league_id != parsed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="source import run not found")
    run = api_store.enqueue_reprocess(user.user_id, parsed)
    if run is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="analytics recompute already queued")
    return to_reprocess_response(api_store, run)


@router.get("/reprocess-runs/{run_id}", operation_id="get_reprocess_run")
async def get_reprocess_run(
    run_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
) -> ReprocessRunResponse:
    parsed = parse_run_id(run_id)
    run = api_store.reprocess_runs[parsed]
    require_league_access(user, api_store, run.league_id)
    return to_reprocess_response(api_store, run)


@router.post("/versions/{version_id}/publish", operation_id="publish_version")
async def publish_version(
    version_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
) -> VersionPublishResponse:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="internal admin required")
    api_store.published_versions.add(VersionId(version_id))
    return VersionPublishResponse(versionId=version_id, alias=CURRENT_VERSION_ALIAS, published=True)


def to_credential_response(credential: EncryptedCredential) -> CredentialResponse:
    return CredentialResponse(
        credentialVersion=credential.credential_version,
        keyId=credential.key_id,
        status=credential.status,
        consentVersion=credential.consent_version,
        expiresAt=credential.expires_at,
        rotatedAt=credential.rotated_at,
        lastValidatedAt=credential.last_validated_at,
    )


def to_run_response(run: ImportRun) -> ImportRunResponse:
    return ImportRunResponse(
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


def to_reprocess_response(api_store: ApiStore, run: ImportRun) -> ReprocessRunResponse:
    source_counts = api_store.current_snapshot_source_counts(run.league_id)
    caveats = api_store.current_snapshot_caveats(run.league_id)
    return ReprocessRunResponse(
        runId=UUID(str(run.id)),
        leagueId=UUID(str(run.league_id)),
        status=run.status,
        step=run.step,
        sourceCounts=source_counts
        if source_counts is not None
        else analytics_repository.dashboard_counts(),
        caveats=[] if caveats is None else caveats,
        warnings=list(run.warnings),
        errorSummary=None,
        createdAt=run.created_at,
    )
