from fastapi import HTTPException, status

from mygm_api.config import get_settings
from mygm_api.security import AlphaUser
from mygm_api.store import ApiStore


def enforce_rate_limit(user: AlphaUser, api_store: ApiStore, action: str) -> None:
    limit = get_settings().rate_limit_attempts
    if not api_store.allow_rate_limited_action(user.user_id, action, limit):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail="rate limit exceeded")
