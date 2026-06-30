from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Response, status

from mygm_api.dependencies import StoreDep, UserDep, parse_league_id, require_league_access
from mygm_api.models import ClaimStatus, CredentialStatus, League
from mygm_api.schemas import (
    CredentialRevokeResponse,
    InviteAcceptRequest,
    InviteAcceptResponse,
    LeagueCreateRequest,
    LeagueListResponse,
    LeagueResponse,
    ManagerClaimCreateRequest,
    ManagerClaimPatchRequest,
    ManagerClaimResponse,
    ProfileResponse,
)

router = APIRouter(tags=["membership"])


@router.get("/me", operation_id="get_current_profile")
async def get_current_profile(user: UserDep, api_store: StoreDep) -> ProfileResponse:
    league_ids = [
        UUID(str(league_id))
        for league_id, users in api_store.memberships.items()
        if user.user_id in users
    ]
    organization_ids = [
        league.org_id
        for league in api_store.leagues.values()
        if api_store.has_league_access(user.user_id, league.id)
    ]
    return ProfileResponse(
        userId=user.user_id,
        email=user.email,
        alphaAccess=api_store.is_invited(user.user_id),
        organizationIds=organization_ids,
        leagueIds=league_ids,
        internalAdmin=user.is_admin,
    )


@router.post(
    "/alpha-invites/accept",
    operation_id="accept_alpha_invite",
)
async def accept_alpha_invite(
    payload: InviteAcceptRequest,
    user: UserDep,
    api_store: StoreDep,
) -> InviteAcceptResponse:
    if payload.email != user.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="invite email mismatch")
    api_store.accept_invite(user.user_id)
    return InviteAcceptResponse(alphaAccess=True, organizationId=UUID(int=1))


@router.get(
    "/organizations/{organization_id}/leagues",
    operation_id="list_organization_leagues",
)
async def list_organization_leagues(
    organization_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
) -> LeagueListResponse:
    leagues = [
        to_league_response(league)
        for league in api_store.leagues.values()
        if league.org_id == organization_id and api_store.has_league_access(user.user_id, league.id)
    ]
    return LeagueListResponse(leagues=leagues)


@router.post(
    "/leagues",
    status_code=status.HTTP_201_CREATED,
    operation_id="create_league",
)
async def create_league(
    payload: LeagueCreateRequest,
    user: UserDep,
    api_store: StoreDep,
) -> LeagueResponse:
    if not api_store.is_invited(user.user_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="alpha invite required")
    league = api_store.create_league(user.user_id, payload.espn_league_id, payload.name)
    return to_league_response(league)


@router.get(
    "/leagues/{league_id}",
    operation_id="get_league",
)
async def get_league(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
) -> LeagueResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    return to_league_response(api_store.leagues[parsed])


@router.post(
    "/manager-claims",
    status_code=status.HTTP_201_CREATED,
    operation_id="create_manager_claim",
)
async def create_manager_claim(
    payload: ManagerClaimCreateRequest,
    user: UserDep,
    api_store: StoreDep,
) -> ManagerClaimResponse:
    league_id = parse_league_id(payload.league_id)
    require_league_access(user, api_store, league_id)
    claim = api_store.create_claim(user.user_id, league_id, payload.espn_team_id)
    return ManagerClaimResponse(
        claimId=claim.id,
        leagueId=UUID(str(claim.league_id)),
        espnTeamId=claim.espn_team_id,
        status=claim.status,
    )


@router.patch(
    "/manager-claims/{claim_id}",
    operation_id="update_manager_claim",
)
async def update_manager_claim(
    claim_id: Annotated[UUID, Path()],
    payload: ManagerClaimPatchRequest,
    user: UserDep,
    api_store: StoreDep,
) -> ManagerClaimResponse:
    claim = api_store.claims[claim_id]
    require_league_access(user, api_store, claim.league_id)
    updated = claim
    if user.is_admin or payload.status == ClaimStatus.REJECTED:
        updated = type(claim)(
            id=claim.id,
            league_id=claim.league_id,
            espn_team_id=claim.espn_team_id,
            status=payload.status,
            requested_by=claim.requested_by,
        )
        api_store.claims[claim_id] = updated
    return ManagerClaimResponse(
        claimId=updated.id,
        leagueId=UUID(str(updated.league_id)),
        espnTeamId=updated.espn_team_id,
        status=updated.status,
    )


@router.delete(
    "/leagues/{league_id}/credentials",
    operation_id="revoke_league_credentials",
)
async def revoke_league_credentials(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
    response: Response,
) -> CredentialRevokeResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    credential = api_store.credentials.get(parsed)
    if credential is None:
        response.status_code = status.HTTP_204_NO_CONTENT
        return CredentialRevokeResponse(status=CredentialStatus.REVOKED)
    api_store.credentials[parsed] = type(credential)(
        league_id=credential.league_id,
        credential_version=credential.credential_version,
        key_id=credential.key_id,
        nonce=credential.nonce,
        ciphertext=credential.ciphertext,
        expires_at=credential.expires_at,
        rotated_at=credential.rotated_at,
        last_validated_at=credential.last_validated_at,
        status=CredentialStatus.REVOKED,
        consent_version=credential.consent_version,
        authorized_by=credential.authorized_by,
        created_by=credential.created_by,
    )
    return CredentialRevokeResponse(status=CredentialStatus.REVOKED)


def to_league_response(league: League) -> LeagueResponse:
    return LeagueResponse(
        leagueId=UUID(str(league.id)),
        organizationId=league.org_id,
        espnLeagueId=league.espn_league_id,
        name=league.name,
        currentVersionId=None,
    )
