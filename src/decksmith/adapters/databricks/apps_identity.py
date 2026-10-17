"""IdentityProvider for Databricks Apps: the user token arrives ONLY in x-forwarded-access-token."""

from __future__ import annotations

from collections.abc import Mapping

from decksmith.domain.errors import AuthenticationError
from decksmith.domain.principal import Principal


class DatabricksAppsIdentity:
    def authenticate(self, headers: Mapping[str, str]) -> Principal:
        lowered = {k.lower(): v for k, v in headers.items()}
        token = lowered.get("x-forwarded-access-token", "")
        user = lowered.get("x-forwarded-email") or lowered.get("x-forwarded-preferred-username", "")
        if not token or not user:
            raise AuthenticationError("Databricks Apps did not forward a user token")
        return Principal(user_id=user, display_name=lowered.get("x-forwarded-preferred-username", user), token=token)
