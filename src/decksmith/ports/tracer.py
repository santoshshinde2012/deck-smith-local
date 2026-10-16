"""Tracer port: one span per graph node, linked by run_id (MLflow 3 tracing in the design)."""

from contextlib import AbstractContextManager
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Tracer(Protocol):
    def span(self, name: str, attributes: dict[str, Any] | None = None) -> AbstractContextManager[Any]: ...
