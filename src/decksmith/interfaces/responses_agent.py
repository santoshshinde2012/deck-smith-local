"""MLflow ResponsesAgent wrapper, so the same graph can be logged and served like on Databricks.

Conversation protocol (custom_inputs):
  start:    the request as the last user message
  decide:   {"run_id": "...", "action": "approve|edit|reject", "feedback": "..."}
Credentials belong only in HTTP headers. Serving integrations authenticate before invoking predict,
or call predict_with_headers; the principal travels in invocation context, outside MLflow inputs.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import wraps
from typing import Any, TypeVar

from mlflow.pyfunc import ResponsesAgent  # type: ignore[attr-defined]
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from decksmith.application.context import acting_as, current_principal
from decksmith.application.service import Action, DeckService, RunView
from decksmith.domain.errors import InvalidParameters
from decksmith.ports.identity import IdentityProvider


class _Options(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    run_id: str | None = Field(default=None, min_length=1, max_length=128)
    action: Action = "approve"
    feedback: str = Field(default="", max_length=2000)


def _validated_request(request: ResponsesAgentRequest | dict[str, Any]) -> ResponsesAgentRequest:
    """Reject credentials and malformed options before MLflow can capture the request or errors."""
    try:
        validated = request if isinstance(request, ResponsesAgentRequest) else ResponsesAgentRequest(**request)
        options = _Options.model_validate(validated.custom_inputs or {})
    except (ValidationError, TypeError, ValueError):
        # ValidationError includes input values; do not echo possible credentials into logs or responses.
        raise InvalidParameters(
            "Invalid Responses request; custom_inputs allows only run_id, action and feedback. "
            "Send credentials in request headers."
        ) from None
    if options.run_id is None:
        _last_user_text(validated)
    return validated.model_copy(update={"custom_inputs": options.model_dump(exclude_defaults=True)})


Agent = TypeVar("Agent", bound=ResponsesAgent)


def _validate_before_tracing(cls: type[Agent]) -> type[Agent]:
    """MLflow wraps predict during class creation; put validation outside that automatic trace."""
    traced_predict = cls.predict

    @wraps(traced_predict)
    def predict(self: Agent, request: ResponsesAgentRequest | dict[str, Any]) -> ResponsesAgentResponse:
        clean_request = _validated_request(request)
        current_principal()  # anonymous direct calls fail before any trace is created
        return traced_predict(self, clean_request)  # type: ignore[no-any-return]

    cls.predict = predict  # type: ignore[method-assign,assignment]
    return cls


@_validate_before_tracing
class DeckSmithResponsesAgent(ResponsesAgent):  # type: ignore[misc]
    def __init__(self, service: DeckService, identity: IdentityProvider) -> None:
        self._service = service
        self._identity = identity

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:  # type: ignore[override]
        custom: dict[str, Any] = dict(request.custom_inputs or {})
        principal = current_principal()
        if custom.get("run_id"):
            view = self._service.decide(
                str(custom["run_id"]), custom.get("action", "approve"), principal, str(custom.get("feedback", ""))
            )
        else:
            view = self._service.start(_last_user_text(request), principal)
        return ResponsesAgentResponse(
            output=[
                self.create_text_output_item(  # type: ignore[list-item]
                    text=summarise(view), id=f"msg_{view.run_id}"
                )
            ],
            custom_outputs=view.model_dump(mode="json"),
        )

    def predict_with_headers(
        self, request: ResponsesAgentRequest | dict[str, Any], headers: Mapping[str, str]
    ) -> ResponsesAgentResponse:
        """Untraced serving boundary: authenticate immutable headers without serializing them."""
        principal = self._identity.authenticate(headers)
        with acting_as(principal):
            return self.predict(request)  # type: ignore[arg-type,no-any-return]


def _last_user_text(request: ResponsesAgentRequest) -> str:
    for item in reversed(request.input):
        data = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        if data.get("role") == "user":
            content = data.get("content")
            if isinstance(content, str):
                return content
            return " ".join(part.get("text", "") for part in content or [] if isinstance(part, dict))
    raise InvalidParameters("A user message is required to start a deck")


def summarise(view: RunView) -> str:
    if view.status == "awaiting_approval" and view.outline:
        titles = "; ".join(s["title_hint"] for s in view.outline["slides"])
        return f"Proposed outline for run {view.run_id}: {titles}. Approve, edit or reject."
    if view.status == "done" and view.artifact:
        return f"Deck ready: {view.artifact['slide_count']} slides, sha256 {view.artifact['sha256'][:12]}."
    if view.error:
        return view.error
    return json.dumps({"run_id": view.run_id, "status": view.status})
