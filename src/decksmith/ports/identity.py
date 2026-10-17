"""IdentityProvider port: turns request credentials into a Principal (OBO on Databricks)."""

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from decksmith.domain.principal import Principal


@runtime_checkable
class IdentityProvider(Protocol):
    def authenticate(self, headers: Mapping[str, str]) -> Principal:
        """Identify the caller from HTTP headers, or raise AuthenticationError."""
        ...
