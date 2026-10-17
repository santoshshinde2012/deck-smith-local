"""Per-invocation context. Keeps the caller's principal (and token) out of persisted graph state."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from decksmith.domain.errors import AuthenticationError
from decksmith.domain.principal import Principal

_current: ContextVar[Principal | None] = ContextVar("decksmith_principal", default=None)


@contextmanager
def acting_as(principal: Principal) -> Iterator[None]:
    token = _current.set(principal)
    try:
        yield
    finally:
        _current.reset(token)


def current_principal() -> Principal:
    principal = _current.get()
    if principal is None:
        raise AuthenticationError("no principal in context")
    return principal
