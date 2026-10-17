"""Local identity: static bearer tokens per test user, or HS256 JWTs. Stand-ins for Apps OBO."""

from __future__ import annotations

from collections.abc import Mapping

import jwt

from decksmith.domain.errors import AuthenticationError
from decksmith.domain.principal import Principal

TEST_USERS = {
    "alice-token": Principal(user_id="alice", display_name="Alice (EU-West only)"),
    "bob-token": Principal(user_id="bob", display_name="Bob (all regions)"),
    "carol-token": Principal(user_id="carol", display_name="Carol (no data access)"),
}


def _bearer(headers: Mapping[str, str]) -> str:
    lowered = {k.lower(): v for k, v in headers.items()}
    token = lowered.get("x-forwarded-access-token") or lowered.get("authorization", "").removeprefix("Bearer ").strip()
    if not token:
        raise AuthenticationError("missing bearer token")
    return token


class StaticTokenIdentity:
    def __init__(self, users: Mapping[str, Principal] | None = None) -> None:
        self._users = dict(users or TEST_USERS)

    def authenticate(self, headers: Mapping[str, str]) -> Principal:
        token = _bearer(headers)
        try:
            principal = self._users[token]
        except KeyError as exc:
            raise AuthenticationError("unknown token") from exc
        return principal.model_copy(update={"token": token})


class JwtIdentity:
    """HS256 tokens signed with a shared secret (e.g. minted by a Keycloak test realm or a script)."""

    def __init__(self, secret: str, audience: str = "decksmith") -> None:
        self._secret = secret
        self._audience = audience

    def authenticate(self, headers: Mapping[str, str]) -> Principal:
        token = _bearer(headers)
        try:
            claims = jwt.decode(token, self._secret, algorithms=["HS256"], audience=self._audience)
        except jwt.PyJWTError as exc:
            raise AuthenticationError(str(exc)) from exc
        return Principal(
            user_id=str(claims["sub"]),
            display_name=str(claims.get("name", "")),
            groups=tuple(claims.get("groups", ())),
            token=token,
        )
