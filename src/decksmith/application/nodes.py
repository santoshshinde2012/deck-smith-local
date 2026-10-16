"""The DeckSmith graph nodes. Each node has one job; collaborators arrive through the constructor."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from decksmith.application import prompts
from decksmith.application.context import current_principal
from decksmith.application.data_fetch import FactFetcher
from decksmith.application.state import DeckState
from decksmith.domain.deckspec import DeckSpec
from decksmith.domain.errors import GuardrailViolation
from decksmith.domain.facts import FactRegistry, format_value
from decksmith.domain.integrity import chart_consistency, numeric_integrity
from decksmith.domain.outline import Intake, Outline
from decksmith.ports.llm import LLMGateway, LLMRequest, LLMResponse, Message, Tier
from decksmith.ports.renderer import Renderer
from decksmith.ports.templates import TemplateRepository
from decksmith.ports.tracer import Tracer

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
    def _call(self, state: DeckState, node: str, tier: Tier, messages: tuple[Message, ...]) -> LLMResponse:
        request = LLMRequest(
            node=node,
            tier=tier,
            messages=messages,
            run_id=state["run_id"],
            user_hash=hashlib.sha256(state.get("user_id", "").encode()).hexdigest()[:16],
        )
        return self._llm.complete(request)

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
        with self._tracer.span("intake", {"run_id": state["run_id"]}):
            response = self._call(state, "intake", "small", prompts.intake_messages(state["request_text"]))
            intake = Intake.model_validate_json(response.text)
            return {"intake": intake.model_dump(), "status": "planning", "usage": self._usage("intake", response)}

    def planner(self, state: DeckState) -> DeckState:
        with self._tracer.span("planner", {"run_id": state["run_id"]}):
            catalog = [
                {"id": t.id, "description": t.description, "kind": t.kind, "params": [p.model_dump() for p in t.params]}
                for t in self._templates.list()
            ]
            messages = prompts.planner_messages(
                state["request_text"], state["intake"], catalog, state.get("feedback", "")
            )
            response = self._call(state, "planner", "small", messages)
            outline = Outline.model_validate_json(response.text)
            for slide in outline.slides:
                for request in slide.data_requests:
                    self._templates.get(request.template_id)  # unknown templates fail here, before approval
            return {
                "outline": outline.model_dump(),
                "status": "awaiting_approval",
                "usage": self._usage("planner", response),
            }

    def await_approval(self, state: DeckState) -> DeckState:
        decision = self._interrupt({"run_id": state["run_id"], "outline": state["outline"]})
        action = str(decision.get("action", "reject"))
        return {
            "approval": {"action": action},
            "feedback": str(decision.get("feedback", "")),
            "status": {"approve": "fetching", "edit": "planning"}.get(action, "rejected"),
        }

    def data_fetch(self, state: DeckState) -> DeckState:
        with self._tracer.span("data_fetch", {"run_id": state["run_id"]}):
            principal = current_principal()
            registry = FactRegistry()
            outline = Outline.model_validate(state["outline"])
            for slide in outline.slides:
                for request in slide.data_requests:
                    self._fetcher.fetch(request, principal, registry)
            if len(registry) == 0:
                return {
                    "facts": [],
                    "status": "no_data",
                    "error": "None of the requested data is visible to you, so no deck was produced.",
                }
            return {"facts": registry.dump(), "status": "writing", "writer_loops": 0}

    def writer(self, state: DeckState) -> DeckState:
        with self._tracer.span("writer", {"run_id": state["run_id"], "loop": state.get("writer_loops", 0)}):
            registry = FactRegistry.load(state["facts"])
            facts = [
                {
                    "id": f.id,
                    "kind": f.kind,
                    "label": f.label,
                    "template_id": f.source.template_id,
                    "display": format_value(f.value, f.format, f.unit) if f.value is not None else None,
                    "categories": list(f.categories),
                }
                for f in registry.all()
            ]
            template_id = state["intake"].get("template_id", "corp_default@1.0")
            messages = prompts.writer_messages(state["outline"], facts, template_id, state.get("issues", []))
            loops = state.get("writer_loops", 0)
            first = loops == 0
            try:
                response = self._call(state, "writer", "strong", messages)
                spec = DeckSpec.model_validate_json(response.text)
            except GuardrailViolation as exc:
                return {
                    "issues": [f"guardrail: {exc}"],
                    "writer_loops": loops + 1,
                    "spec": {},
                    "schema_valid_first_try": False if first else state.get("schema_valid_first_try", False),
                }
            except (ValidationError, json.JSONDecodeError) as exc:
                return {
                    "issues": [f"schema: {exc}"[:500]],
                    "writer_loops": loops + 1,
                    "spec": {},
                    "schema_valid_first_try": False if first else state.get("schema_valid_first_try", False),
                }
            update: DeckState = {
                "spec": spec.model_dump(),
                "writer_loops": loops + 1,
                "usage": self._usage("writer", response),
            }
            if first:
                update["schema_valid_first_try"] = True
            return update

    def check(self, state: DeckState) -> DeckState:
        """Deterministic QA gate before rendering: facts resolve, no bare digits, charts plot series."""
        with self._tracer.span("qa", {"run_id": state["run_id"]}):
            if not state.get("spec"):
                return {"status": "writing"}
            spec = DeckSpec.model_validate(state["spec"])
            registry = FactRegistry.load(state["facts"])
            issues = numeric_integrity(spec, registry) + chart_consistency(spec, registry)
            text = [f"{i.slide_id} {i.code}: {i.detail}" for i in issues]
            return {"issues": text, "status": "rendering" if not issues else "writing"}

    def render(self, state: DeckState) -> DeckState:
        with self._tracer.span("render", {"run_id": state["run_id"]}):
            spec = DeckSpec.model_validate(state["spec"])
            deck = self._renderer.render(spec, FactRegistry.load(state["facts"]), state["run_id"])
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

    @staticmethod
    def failed(state: DeckState) -> DeckState:
        return {
            "status": "failed",
            "error": "QA failed after the maximum number of writer loops: " + "; ".join(state.get("issues", []))[:800],
        }
