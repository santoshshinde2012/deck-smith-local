"""MLflow ResponsesAgent wrapper, so the same graph can be logged and served like on Databricks.

Conversation protocol (custom_inputs):
  start:    {"access_token": "..."} and the request as the last user message
  decide:   {"access_token": "...", "run_id": "...", "action": "approve|edit|reject", "feedback": "..."}
Locally the caller's token travels in custom_inputs [A]; on Databricks the endpoint receives OBO credentials.
"""

from __future__ import annotations

import json
from typing import Any

from mlflow.pyfunc import ResponsesAgent  # type: ignore[attr-defined]
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse

from decksmith.application.service import DeckService, RunView
from decksmith.ports.identity import IdentityProvider


class DeckSmithResponsesAgent(ResponsesAgent):  # type: ignore[misc]
    def __init__(self, service: DeckService, identity: IdentityProvider) -> None:
        self._service = service
        self._identity = identity

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:  # type: ignore[override]
        custom: dict[str, Any] = dict(request.custom_inputs or {})
        principal = self._identity.authenticate({"authorization": f"Bearer {custom.get('access_token', '')}"})
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


def _last_user_text(request: ResponsesAgentRequest) -> str:
    for item in reversed(request.input):
        data = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        if data.get("role") == "user":
            content = data.get("content")
            if isinstance(content, str):
                return content
            return " ".join(part.get("text", "") for part in content or [] if isinstance(part, dict))
    raise ValueError("no user message in the request")


def summarise(view: RunView) -> str:
    if view.status == "awaiting_approval" and view.outline:
        titles = "; ".join(s["title_hint"] for s in view.outline["slides"])
        return f"Proposed outline for run {view.run_id}: {titles}. Approve, edit or reject."
    if view.status == "done" and view.artifact:
        return f"Deck ready: {view.artifact['slide_count']} slides, sha256 {view.artifact['sha256'][:12]}."
    if view.error:
        return view.error
    return json.dumps({"run_id": view.run_id, "status": view.status})
