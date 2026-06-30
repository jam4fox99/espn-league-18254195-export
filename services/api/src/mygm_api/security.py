from dataclasses import dataclass
from typing import Annotated, Final, NewType

from fastapi import Depends, Header, HTTPException, status

UserId = NewType("UserId", str)
TOKEN_PART_COUNT: Final[int] = 4


@dataclass(frozen=True, slots=True)
class AlphaUser:
    user_id: UserId
    email: str
    is_admin: bool


@dataclass(frozen=True, slots=True)
class MissingBearerToken:
    reason: str


@dataclass(frozen=True, slots=True)
class InvalidBearerToken:
    reason: str


type AuthResult = AlphaUser | MissingBearerToken | InvalidBearerToken


class DevBearerVerifier:
    def verify(self, authorization: str | None) -> AuthResult:
        if authorization is None:
            return MissingBearerToken(reason="missing authorization header")
        scheme, separator, token = authorization.partition(" ")
        if separator == "" or scheme.lower() != "bearer":
            return InvalidBearerToken(reason="authorization must use bearer scheme")
        parts = token.split(":")
        if len(parts) != TOKEN_PART_COUNT or parts[0] != "alpha":
            return InvalidBearerToken(reason="unsupported alpha token")
        return AlphaUser(
            user_id=UserId(parts[1]),
            email=parts[2],
            is_admin=parts[3] == "admin",
        )


verifier = DevBearerVerifier()


def get_current_user(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> AlphaUser:
    result = verifier.verify(authorization)
    match result:
        case AlphaUser():
            return result
        case MissingBearerToken(reason=reason):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=reason)
        case InvalidBearerToken(reason=reason):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=reason)


CurrentUser = Annotated[AlphaUser, Depends(get_current_user)]
