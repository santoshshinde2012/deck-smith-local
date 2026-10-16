"""Domain errors. Adapters translate infrastructure failures into these."""


class DeckSmithError(Exception):
    """Base class for every DeckSmith error."""


class AccessDenied(DeckSmithError):
    """The principal may not see the requested data."""


class NoDataAvailable(DeckSmithError):
    """Every data request returned no rows for this principal."""


class UnknownTemplate(DeckSmithError):
    """A data request named a SQL template that does not exist."""


class InvalidParameters(DeckSmithError):
    """A data request's parameters failed validation against its template."""


class GuardrailViolation(DeckSmithError):
    """LLM output broke a guardrail (mirrors Portkey's 446 deny status)."""

    status_code = 446


class AuthenticationError(DeckSmithError):
    """The caller could not be identified."""


class RunNotFound(DeckSmithError):
    """No deck run exists with the given id."""
