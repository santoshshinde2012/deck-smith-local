"""Gateway decorators (open/closed): add policy around any LLMGateway without changing it."""

from __future__ import annotations

import json

from decksmith.domain.errors import GuardrailViolation
from decksmith.domain.integrity import contains_bare_digit
from decksmith.ports.llm import LLMGateway, LLMRequest, LLMResponse

_TEXT_FIELDS = ("title", "subtitle", "bullets", "label")


class NoBareNumbersGuardrail:
    """Client-side twin of the design's Portkey 'pg-no-bare-numbers' output guardrail (446 on deny).

    Applies to the Writer only. Production enforces it in Portkey Enterprise as well; the deterministic
    QA check in the graph is the second, independent line.
    """

    def __init__(self, inner: LLMGateway, nodes: frozenset[str] = frozenset({"writer"})) -> None:
        self._inner = inner
        self._nodes = nodes

    def complete(self, request: LLMRequest) -> LLMResponse:
        response = self._inner.complete(request)
        if request.node in self._nodes and _has_bare_number(response.text):
            raise GuardrailViolation(f"{request.node}: digits outside {{{{fact:id}}}} placeholders")
        return response


def _has_bare_number(text: str) -> bool:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return False  # schema validation reports malformed output; this guardrail only judges text fields
    return any(contains_bare_digit(t) for t in _texts(payload))


def _texts(node: object) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _TEXT_FIELDS:
                found += (
                    [value]
                    if isinstance(value, str)
                    else [v for v in value if isinstance(v, str)]
                    if isinstance(value, list)
                    else []
                )
            else:
                found += _texts(value)
    elif isinstance(node, list):
        for item in node:
            found += _texts(item)
    return found
