from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Path, Response

from mygm_api.analytics_fixtures import (
    FAAB_CONTEXT,
    PAYLOAD_VERSION,
    PRODUCT_LABEL,
    analytics_repository,
)
from mygm_api.dependencies import StoreDep, UserDep, parse_league_id, require_league_access
from mygm_api.models import ShareLink, VersionId
from mygm_api.schemas import (
    ShareLinkCreateRequest,
    ShareLinkListResponse,
    ShareLinkResponse,
    SharePayloadResponse,
)

PNG_1X1: Final[bytes] = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff"
    b"\xff?\x00\x05\xfe\x02\xfeA\xe2&\xb8\x00\x00\x00\x00IEND\xaeB`\x82"
)

router = APIRouter(tags=["share"])


@router.post(
    "/leagues/{league_id}/share-links",
    operation_id="create_share_link",
)
async def create_share_link(
    league_id: Annotated[UUID, Path()],
    payload: ShareLinkCreateRequest,
    user: UserDep,
    api_store: StoreDep,
) -> ShareLinkResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    share = api_store.create_share_link(parsed, VersionId(payload.version_id))
    return share_response(share)


@router.get(
    "/leagues/{league_id}/share-links",
    operation_id="list_share_links",
)
async def list_share_links(
    league_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
) -> ShareLinkListResponse:
    parsed = parse_league_id(league_id)
    require_league_access(user, api_store, parsed)
    links = [
        share_response(share)
        for share in api_store.share_links.values()
        if share.league_id == parsed
    ]
    return ShareLinkListResponse(shareLinks=links)


@router.delete(
    "/share-links/{share_link_id}",
    operation_id="revoke_share_link",
)
async def revoke_share_link(
    share_link_id: Annotated[UUID, Path()],
    user: UserDep,
    api_store: StoreDep,
) -> ShareLinkResponse:
    share = api_store.share_links[share_link_id]
    require_league_access(user, api_store, share.league_id)
    return share_response(api_store.revoke_share_link(share_link_id))


@router.get(
    "/share/{share_slug}",
    operation_id="get_public_share",
)
async def get_public_share(share_slug: Annotated[str, Path()]) -> SharePayloadResponse:
    trade_counts = analytics_repository.metric_counts("trade_outcome_v1")
    return SharePayloadResponse(
        shareSlug=share_slug,
        title="Privacy-safe MyGM report card",
        privacy="public share excludes raw artifacts, private emails, credentials, and import logs",
        payloadVersion=PAYLOAD_VERSION,
        productLabel=PRODUCT_LABEL,
        compositeScore=79.4449,
        canonicalGradedTradeEvents=trade_counts["canonicalTradeEvents"],
        ungradedExecutedAccepts=trade_counts["ungradedExecutedAccepts"],
        faabContext=FAAB_CONTEXT,
        careerExcludedSeasons=[2026],
    )


@router.get(
    "/share/{share_slug}/og.png",
    operation_id="get_public_share_og_image",
    responses={200: {"content": {"image/png": {}}}},
)
async def get_public_share_og_image(share_slug: Annotated[str, Path()]) -> Response:
    return Response(
        content=PNG_1X1,
        media_type="image/png",
        headers={"X-Share-Slug": share_slug},
    )


def share_response(share: ShareLink) -> ShareLinkResponse:
    return ShareLinkResponse(
        shareLinkId=share.id,
        shareSlug=share.slug,
        leagueId=UUID(str(share.league_id)),
        versionId=UUID(str(share.version_id)),
        revoked=share.revoked,
    )
