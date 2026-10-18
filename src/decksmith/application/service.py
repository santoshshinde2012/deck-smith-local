"""DeckService: the use cases the API, UI and ResponsesAgent call (start, decide, get)."""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from langgraph.types import Command
from pydantic import BaseModel

from decksmith.application.context import acting_as
from decksmith.application.trace_records import invocation_output
from decksmith.domain.errors import RunNotFound
from decksmith.domain.principal import Principal
from decksmith.observability import bind_run_id, get_logger, reset_run_id
from decksmith.ports.tracer import SpanKind, Tracer

log = get_logger(__name__)

Action = Literal["approve", "edit", "reject"]


class RunView(BaseModel):
    run_id: str
    status: str
    outline: dict[str, Any] | None = None
    artifact: dict[str, Any] | None = None
    spec: dict[str, Any] | None = None
    facts: list[dict[str, Any]] = []
    issues: list[str] = []
    error: str = ""
    schema_valid_first_try: bool | None = None
    usage: list[dict[str, Any]] = []


class DeckService:
    def __init__(self, graph: Any, tracer: Tracer) -> None:
        self._graph = graph
        self._tracer = tracer

    @staticmethod
    def _config(run_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": run_id}}

    def start(self, request_text: str, principal: Principal, run_id: str | None = None) -> RunView:
        run_id = run_id or uuid.uuid4().hex
        state = {
            "run_id": run_id,
            "user_id": principal.user_id,
            "request_text": request_text,
            "status": "intake",
            "usage": [],
        }
        return self._run(
            run_id,
            principal,
            state,
            "run_started",
            trace_name="draft",
            trace_inputs={
                "request": request_text,
                "user_id": principal.user_id,
                "display_name": principal.display_name,
                "run_id": run_id,
            },
        )

    def decide(self, run_id: str, action: Action, principal: Principal, feedback: str = "") -> RunView:
        self._owned(run_id, principal)
        return self._run(
            run_id,
            principal,
            Command(resume={"action": action, "feedback": feedback}),
            "run_decided",
            trace_name="decision",
            trace_inputs={
                "run_id": run_id,
                "user_id": principal.user_id,
                "display_name": principal.display_name,
                "action": action,
                "feedback": feedback,
            },
            action=action,
        )

    def _run(
        self,
        run_id: str,
        principal: Principal,
        graph_input: Any,
        event: str,
        *,
        trace_name: str,
        trace_inputs: dict[str, Any],
        **fields: str,
    ) -> RunView:
        token = bind_run_id(run_id)
        started = time.perf_counter()
        try:
            log.info(event, extra=fields)
            with self._tracer.span(trace_name, {"run_id": run_id}, span_type=SpanKind.WORKFLOW) as span:
                span.set_inputs(trace_inputs)
                try:
                    with acting_as(principal):
                        self._graph.invoke(graph_input, self._config(run_id))
                    view = self.get(run_id, principal)
                except Exception:
                    span.set_outputs({"run_id": run_id, "status": "error"})
                    raise
                span.set_outputs(invocation_output(view))
            log.info(
                "run_step_finished",
                extra={
                    "status": view.status,
                    "facts": len(view.facts),
                    "duration_ms": round((time.perf_counter() - started) * 1000),
                },
            )
            return view
        finally:
            reset_run_id(token)

    def get(self, run_id: str, principal: Principal) -> RunView:
        values = self._owned(run_id, principal)
        return RunView(
            run_id=run_id,
            status=values.get("status", "unknown"),
            outline=values.get("outline"),
            artifact=values.get("artifact"),
            spec=values.get("spec") or None,
            facts=values.get("facts", []),
            issues=values.get("issues", []),
            error=values.get("error", ""),
            schema_valid_first_try=values.get("schema_valid_first_try"),
            usage=values.get("usage", []),
        )

    def _owned(self, run_id: str, principal: Principal) -> dict[str, Any]:
        snapshot = self._graph.get_state(self._config(run_id))
        values: dict[str, Any] = dict(snapshot.values or {})
        if not values or values.get("user_id") != principal.user_id:
            raise RunNotFound(run_id)  # other users' runs are indistinguishable from missing ones
        return values
