"""Error taxonomy. Adapters translate infrastructure failures into these.

Every error has a stable machine-readable ``code``, a ``category`` and an HTTP ``status_code``.
Interfaces map errors generically from these attributes (no isinstance chains), so a new error
needs no interface change. The table is documented in docs/errors.md.
"""

from __future__ import annotations

from typing import ClassVar, Literal

Category = Literal["client", "auth", "policy", "data", "upstream", "internal"]


class DeckSmithError(Exception):
    """Base class for every DeckSmith error."""

    code: ClassVar[str] = "internal_error"
    category: ClassVar[Category] = "internal"
    status_code: ClassVar[int] = 500
    retryable: ClassVar[bool] = False


class AuthenticationError(DeckSmithError):
    """The caller could not be identified."""

    code, category, status_code = "authentication_failed", "auth", 401


class AccessDenied(DeckSmithError):
    """The principal may not see the requested data."""

    code, category, status_code = "access_denied", "policy", 403


class RunNotFound(DeckSmithError):
    """No deck run exists with the given id for this principal (other users' runs look the same)."""

    code, category, status_code = "run_not_found", "client", 404


class InvalidParameters(DeckSmithError):
    """A data request's parameters failed validation against its template."""

    code, category, status_code = "invalid_parameters", "client", 422


class UnknownTemplate(DeckSmithError):
    """A data request named a SQL template that does not exist."""

    code, category, status_code = "unknown_template", "client", 422


class NoDataAvailable(DeckSmithError):
    """Every data request returned no rows for this principal."""

    code, category, status_code = "no_data", "data", 409


class GuardrailViolation(DeckSmithError):
    """LLM output broke a guardrail (mirrors Portkey's 446 deny status)."""

    code, category, status_code = "guardrail_violation", "policy", 446


class UpstreamError(DeckSmithError):
    """A dependency (warehouse, gateway, catalog) failed or timed out."""

    code, category, status_code, retryable = "upstream_unavailable", "upstream", 503, True


class ConfigurationError(DeckSmithError):
    """The settings select an invalid adapter combination or miss a required value."""

    code, category, status_code = "configuration_error", "internal", 500


ALL_ERRORS: tuple[type[DeckSmithError], ...] = (
    DeckSmithError,
    AuthenticationError,
    AccessDenied,
    RunNotFound,
    InvalidParameters,
    UnknownTemplate,
    NoDataAvailable,
    GuardrailViolation,
    UpstreamError,
    ConfigurationError,
)
