"""Tracer adapters: no-op, and MLflow 3 tracing (OSS server locally, Databricks-managed in production).

Nested ``start_span`` calls become one trace. The root span's inputs and outputs are the request
and response previews in the MLflow traces list. Payloads are truncated, and keys that look like
credentials are dropped before they reach the tracking store.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from typing import Any

_TEXT_LIMIT = 1500
_DEPTH_LIMIT = 6
_COLLECTION_LIMIT = 40
_SECRET_KEYS = frozenset(
    {
        "token",
        "authorization",
        "secret",
        "password",
        "api_key",
        "access_token",
        "refresh_token",
        "credential",
        "credentials",
    }
)


def _sensitive(key: str) -> bool:
    folded = key.lower().replace("-", "_")
    return (
        folded in _SECRET_KEYS
        or folded.endswith("_token")
        or folded.endswith("_secret")
        or "password" in folded
        or "api_key" in folded
    )


def _clip(text: str) -> str:
    if len(text) <= _TEXT_LIMIT:
        return text
    return text[: _TEXT_LIMIT - 3] + "..."


def sanitize(value: Any, depth: int = 0) -> Any:
    """Return a JSON-friendly copy with long text cut and credential-shaped keys removed."""
    if depth > _DEPTH_LIMIT:
        return "..."
    if isinstance(value, str):
        return _clip(value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, dict):
        kept = [(str(key), item) for key, item in value.items() if not _sensitive(str(key))]
        return {key: sanitize(item, depth + 1) for key, item in kept[:_COLLECTION_LIMIT]}
    if isinstance(value, (list, tuple)):
        return [sanitize(item, depth + 1) for item in list(value)[:_COLLECTION_LIMIT]]
    return _clip(str(value))


class _NoopSpan:
    def set_inputs(self, inputs: Any) -> None:
        return None

    def set_outputs(self, outputs: Any) -> None:
        return None

    def set_attribute(self, key: str, value: Any) -> None:
        return None


class NoopTracer:
    def span(self, name: str, attributes: dict[str, Any] | None = None, *, span_type: str = "UNKNOWN") -> Any:
        del name, attributes, span_type
        return nullcontext(_NoopSpan())


class _MlflowSpan:
    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def set_inputs(self, inputs: Any) -> None:
        self._inner.set_inputs(sanitize(inputs))

    def set_outputs(self, outputs: Any) -> None:
        self._inner.set_outputs(sanitize(outputs))

    def set_attribute(self, key: str, value: Any) -> None:
        if _sensitive(key):
            return
        self._inner.set_attribute(key, sanitize(value))


class MlflowTracer:
    def __init__(self, tracking_uri: str, experiment: str) -> None:
        import mlflow

        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment)
        self._mlflow = mlflow

    @contextmanager
    def span(
        self, name: str, attributes: dict[str, Any] | None = None, *, span_type: str = "UNKNOWN"
    ) -> Iterator[_MlflowSpan]:
        safe_attributes = sanitize(attributes or {})
        with self._mlflow.start_span(name=name, span_type=span_type, attributes=safe_attributes) as span:
            yield _MlflowSpan(span)
