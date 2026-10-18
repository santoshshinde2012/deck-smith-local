"""Tracer port: one trace per graph invocation, with a child span per node.

MLflow 3 is the local and Databricks adapter. Application code records plain values on this port
and never imports the tracing library.
"""

from contextlib import AbstractContextManager
from typing import Any, Protocol, runtime_checkable


class SpanKind:
    """Span type names. They match MLflow's SpanType values without importing MLflow."""

    WORKFLOW = "WORKFLOW"
    CHAIN = "CHAIN"
    CHAT_MODEL = "CHAT_MODEL"
    RETRIEVER = "RETRIEVER"
    TOOL = "TOOL"
    GUARDRAIL = "GUARDRAIL"
    TASK = "TASK"


@runtime_checkable
class Span(Protocol):
    def set_inputs(self, inputs: Any) -> None: ...

    def set_outputs(self, outputs: Any) -> None: ...

    def set_attribute(self, key: str, value: Any) -> None: ...


@runtime_checkable
class Tracer(Protocol):
    def span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        *,
        span_type: str = "UNKNOWN",
    ) -> AbstractContextManager[Span]: ...
