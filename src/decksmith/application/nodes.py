"""The DeckSmith graph nodes. Each node has one job; collaborators arrive through the constructor."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from langgraph.errors import GraphInterrupt
from pydantic import ValidationError

from decksmith.application import prompts
from decksmith.application.context import current_principal
from decksmith.application.data_fetch import FactFetcher
from decksmith.application.sql import validate_params
from decksmith.application.state import DeckState
from decksmith.application.trace_records import fact_record, fact_records, message_records, outline_record, spec_record
from decksmith.domain.deckspec import DeckSpec
from decksmith.domain.errors import AccessDenied, GuardrailViolation
from decksmith.domain.facts import FactRegistry, format_value
from decksmith.domain.integrity import Issue, chart_consistency, numeric_integrity, outline_consistency, source_coverage
from decksmith.domain.outline import Intake, Outline
from decksmith.ports.llm import LLMGateway, LLMRequest, LLMResponse, Message, Tier
from decksmith.ports.renderer import Renderer
from decksmith.ports.templates import TemplateRepository
from decksmith.ports.tracer import SpanKind, Tracer

MAX_WRITER_LOOPS = 2

Interrupt = Callable[[Any], Any]


class DeckNodes:
    def __init__(
        self,
        llm: LLMGateway,
        fetcher: FactFetcher,
        templates: TemplateRepository,
        renderer: Renderer,
        tracer: Tracer,
        interrupt: Interrupt,
    ) -> None:
        self._llm = llm
        self._fetcher = fetcher
        self._templates = templates
        self._renderer = renderer
        self._tracer = tracer
        self._interrupt = interrupt

    # --- helpers -------------------------------------------------------------------------
    def _open(self, name: str, state: DeckState, span_type: str, **attributes: Any) -> Any:
        return self._tracer.span(name, {"run_id": state["run_id"], **attributes}, span_type=span_type)

    def _call(self, state: DeckState, node: str, tier: Tier, messages: tuple[Message, ...]) -> LLMResponse:
        request = LLMRequest(
            node=node,
            tier=tier,
            messages=messages,
            run_id=state["run_id"],
            user_hash=hashlib.sha256(state.get("user_id", "").encode()).hexdigest()[:16],
        )
        failure: GuardrailViolation | None = None
        with self._open(f"{node}.model", state, SpanKind.CHAT_MODEL, tier=tier) as span:
            span.set_inputs({"tier": tier, "messages": message_records(messages)})
            try:
                response = self._llm.complete(request)
            except GuardrailViolation as exc:
                span.set_outputs({"accepted": False, "reason": "digits outside fact placeholders"})
                failure = exc
            else:
                span.set_outputs(
                    {
                        "model": response.model,
                        "text": response.text,
                        "prompt_tokens": response.prompt_tokens,
                        "completion_tokens": response.completion_tokens,
                        "accepted": True,
                    }
                )
                return response
        if failure is not None:
            raise failure
        raise GuardrailViolation(node)

    @staticmethod
    def _usage(node: str, response: LLMResponse) -> list[dict[str, Any]]:
        return [
            {
                "node": node,
                "model": response.model,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
            }
        ]

    # --- nodes ---------------------------------------------------------------------------
    def intake(self, state: DeckState) -> DeckState:
        with self._open("intake", state, SpanKind.CHAIN) as span:
            span.set_inputs({"request": state["request_text"], "run_id": state["run_id"]})
            response = self._call(state, "intake", "small", prompts.intake_messages(state["request_text"]))
            intake = Intake.model_validate_json(response.text)
            span.set_outputs(intake.model_dump())
            return {"intake": intake.model_dump(), "status": "planning", "usage": self._usage("intake", response)}

    def planner(self, state: DeckState) -> DeckState:
        with self._open("planner", state, SpanKind.CHAIN) as span:
            catalog = [
                {"id": t.id, "description": t.description, "kind": t.kind, "params": [p.model_dump() for p in t.params]}
                for t in self._templates.list()
            ]
            messages = prompts.planner_messages(
                state["request_text"], state["intake"], catalog, state.get("feedback", "")
            )
            span.set_inputs({"request": state["request_text"], "feedback": state.get("feedback", "")})
            response = self._call(state, "planner", "small", messages)
            outline = Outline.model_validate_json(response.text)
            for slide in outline.slides:
                for request in slide.data_requests:
                    template = self._templates.get(request.template_id)
                    validate_params(template, request.params)  # reject the entire plan before approval or queries
            recorded = outline.model_dump()
            span.set_outputs(outline_record(recorded))
            return {
                "outline": recorded,
                "status": "awaiting_approval",
                "usage": self._usage("planner", response),
            }

    def await_approval(self, state: DeckState) -> DeckState:
        paused: GraphInterrupt | None = None
        with self._open("await_approval", state, SpanKind.TASK) as span:
            span.set_inputs({"run_id": state["run_id"], "outline": outline_record(state.get("outline"))})
            try:
                decision = self._interrupt({"run_id": state["run_id"], "outline": state["outline"]})
            except GraphInterrupt as exc:
                span.set_outputs({"status": "awaiting_approval"})
                paused = exc
            else:
                action = str(decision.get("action", "reject"))
                feedback = str(decision.get("feedback", ""))
                span.set_outputs({"action": action, "feedback": feedback})
                return {
                    "approval": {"action": action},
                    "feedback": feedback,
                    "status": {"approve": "fetching", "edit": "planning"}.get(action, "rejected"),
                }
        if paused is not None:
            raise paused
        raise RuntimeError("approval produced neither a decision nor a pause")

    def data_fetch(self, state: DeckState) -> DeckState:
        with self._open("data_fetch", state, SpanKind.RETRIEVER) as span:
            principal = current_principal()
            registry = FactRegistry()
            outline = Outline.model_validate(state["outline"])
            requests = [request for slide in outline.slides for request in slide.data_requests]
            span.set_inputs(
                {
                    "run_id": state["run_id"],
                    "user_id": principal.user_id,
                    "queries": [{"template_id": request.template_id, "label": request.label} for request in requests],
                }
            )
            denied = empty = False
            for request in requests:
                with self._tracer.span(
                    f"query.{request.template_id}", {"run_id": state["run_id"]}, span_type=SpanKind.RETRIEVER
                ) as query:
                    query.set_inputs(
                        {"template_id": request.template_id, "label": request.label, "params": dict(request.params)}
                    )
                    try:
                        fact = self._fetcher.fetch(request, principal, registry)
                    except AccessDenied:
                        denied = True
                        query.set_outputs({"status": "denied"})
                        continue
                    if fact is None:
                        empty = True
                        query.set_outputs({"status": "empty"})
                    else:
                        query.set_outputs(fact_record(fact.model_dump(mode="json")))
            if denied or empty or len(registry) == 0:
                error = _no_data_message(denied=denied, empty=empty, partial=len(registry) > 0)
                span.set_outputs({"status": "no_data", "error": error, "facts": fact_records(registry.dump())})
                return {"facts": [], "status": "no_data", "error": error}
            dumped = registry.dump()
            span.set_outputs({"status": "writing", "facts": fact_records(dumped)})
            return {"facts": dumped, "status": "writing", "writer_loops": 0}

    def writer(self, state: DeckState) -> DeckState:
        loops = state.get("writer_loops", 0)
        with self._open("writer", state, SpanKind.CHAIN, loop=loops) as span:
            registry = FactRegistry.load(state["facts"])
            facts = [
                {
                    "id": f.id,
                    "kind": f.kind,
                    "label": f.label,
                    "template_id": f.source.template_id,
                    "display": format_value(f.value, f.format, f.unit) if f.value is not None else None,
                    "categories": list(f.categories),
                    "values": list(f.values),
                    "format": f.format,
                    "unit": f.unit,
                }
                for f in registry.all()
            ]
            template_id = state["intake"].get("template_id", "corp_default@1.0")
            messages = prompts.writer_messages(state["outline"], facts, template_id, state.get("issues", []))
            span.set_inputs(
                {
                    "loop": loops,
                    "outline": outline_record(state.get("outline")),
                    "facts": fact_records(registry.dump()),
                }
            )
            first = loops == 0
            try:
                response = self._call(state, "writer", "strong", messages)
                spec = DeckSpec.model_validate_json(response.text)
            except GuardrailViolation as exc:
                self._guardrail_span(state, accepted=False)
                span.set_outputs({"schema_valid": False, "reason": "guardrail"})
                return {
                    "issues": [f"guardrail: {exc}"],
                    "writer_loops": loops + 1,
                    "spec": {},
                    "schema_valid_first_try": False if first else state.get("schema_valid_first_try", False),
                }
            except (ValidationError, json.JSONDecodeError) as exc:
                self._guardrail_span(state, accepted=True)
                span.set_outputs({"schema_valid": False, "reason": "schema"})
                return {
                    "issues": [f"schema: {exc}"[:500]],
                    "writer_loops": loops + 1,
                    "spec": {},
                    "schema_valid_first_try": False if first else state.get("schema_valid_first_try", False),
                }
            self._guardrail_span(state, accepted=True)
            recorded = spec.model_dump()
            span.set_outputs({"schema_valid": True, "spec": spec_record(recorded)})
            update: DeckState = {
                "spec": recorded,
                "writer_loops": loops + 1,
                "usage": self._usage("writer", response),
            }
            if first:
                update["schema_valid_first_try"] = True
            return update

    def _guardrail_span(self, state: DeckState, *, accepted: bool) -> None:
        with self._open("guardrail", state, SpanKind.GUARDRAIL) as span:
            span.set_inputs({"node": "writer"})
            span.set_outputs({"accepted": accepted, "reason": "" if accepted else "digits outside fact placeholders"})

    def check(self, state: DeckState) -> DeckState:
        """Check references, charts, sources and the approved structure before rendering."""
        with self._open("check", state, SpanKind.GUARDRAIL) as span:
            if not state.get("spec"):
                span.set_outputs({"status": "writing", "issues": state.get("issues", [])})
                return {"status": "writing"}
            spec = DeckSpec.model_validate(state["spec"])
            registry = FactRegistry.load(state["facts"])
            issues = (
                numeric_integrity(spec, registry)
                + chart_consistency(spec, registry)
                + source_coverage(spec)
                + outline_consistency(spec, Outline.model_validate(state["outline"]))
            )
            expected_template = state["intake"].get("template_id", "corp_default@1.0")
            if spec.template_id != expected_template:
                issues.append(Issue("deck", "template_mismatch", str(expected_template)))
            text = [f"{i.slide_id} {i.code}: {i.detail}" for i in issues]
            span.set_inputs({"title": spec.title, "slide_count": len(spec.slides)})
            span.set_outputs({"status": "rendering" if not issues else "writing", "issues": text})
            return {"issues": text, "status": "rendering" if not issues else "writing"}

    def render(self, state: DeckState) -> DeckState:
        with self._open("render", state, SpanKind.TOOL) as span:
            spec = DeckSpec.model_validate(state["spec"])
            span.set_inputs({"title": spec.title, "slide_count": len(spec.slides)})
            deck = self._renderer.render(spec, FactRegistry.load(state["facts"]), state["run_id"])
            span.set_outputs({"slide_count": deck.slide_count, "sha256": deck.sha256[:12]})
            return {"artifact": deck.model_dump(), "status": "done"}

    # --- routing -------------------------------------------------------------------------
    @staticmethod
    def route_approval(state: DeckState) -> str:
        return {"approve": "data_fetch", "edit": "planner"}.get(state["approval"]["action"], "__end__")

    @staticmethod
    def route_fetch(state: DeckState) -> str:
        return "__end__" if state.get("status") == "no_data" else "writer"

    @staticmethod
    def route_check(state: DeckState) -> str:
        if state.get("status") == "rendering":
            return "render"
        return "writer" if state.get("writer_loops", 0) < MAX_WRITER_LOOPS + 1 else "failed"

    def failed(self, state: DeckState) -> DeckState:
        error = "QA failed after the maximum number of writer loops: " + "; ".join(state.get("issues", []))[:800]
        with self._open("failed", state, SpanKind.TASK) as span:
            span.set_inputs({"issues": state.get("issues", [])})
            span.set_outputs({"status": "failed", "error": error})
        return {"status": "failed", "error": error}


def _no_data_message(*, denied: bool, empty: bool, partial: bool) -> str:
    """Explain a refusal without guessing: a denial is known, but an empty result has two possible causes."""
    if not denied and not empty:
        return "The approved outline requests no data, so no deck was produced."
    if not partial and not empty:
        return "None of the requested data is visible to you, so no deck was produced."
    if not partial and not denied:
        return (
            "None of the requested queries returned data for you, so no deck was produced. "
            "The period may have no data yet, or row-level policies may hide it."
        )
    if denied and empty:
        cause = "Some requested data is not visible to you, and some requested queries returned no data"
    elif denied:
        cause = "Some requested data is not visible to you"
    else:
        cause = "Some requested queries returned no data"
    return f"{cause}, so no deck was produced. Revise the request and approve a new outline."
