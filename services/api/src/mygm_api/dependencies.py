from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status

from mygm_api.models import LeagueId, RunId
from mygm_api.security import AlphaUser, CurrentUser
from mygm_api.store import ApiStore

store = ApiStore()


def get_store() -> ApiStore:
    return store


StoreDep = Annotated[ApiStore, Depends(get_store)]
UserDep = CurrentUser


def require_alpha_access(user: AlphaUser, api_store: ApiStore) -> None:
    if not api_store.is_invited(user.user_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="alpha invite required")


def parse_league_id(value: UUID) -> LeagueId:
    return LeagueId(value)


def parse_run_id(value: UUID) -> RunId:
    return RunId(value)


def require_league_access(user: AlphaUser, api_store: ApiStore, league_id: LeagueId) -> None:
    require_alpha_access(user, api_store)
    if not api_store.has_league_access(user.user_id, league_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="league membership required")
