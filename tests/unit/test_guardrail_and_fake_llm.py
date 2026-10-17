import json

import pytest

from decksmith.adapters.local.fake_llm import FakeLLM
from decksmith.application.guardrails import NoBareNumbersGuardrail
from decksmith.domain.errors import GuardrailViolation
from decksmith.ports.llm import LLMRequest, Message


def _writer_request() -> LLMRequest:
    payload = {
        "outline": {
            "deck_title": "Retention",
            "audience": "exec",
            "period": "2026-Q3",
            "slides": [{"slide_id": "s02", "layout": "kpi", "title_hint": "KPIs", "data_requests": []}],
        },
        "facts": [{"id": "f1", "template_id": "churn_rate_quarter"}],
        "template_id": "corp_default@1.0",
        "fix_issues": [],
    }
    return LLMRequest(
        node="writer", tier="strong", run_id="r1", messages=(Message(role="user", content=json.dumps(payload)),)
    )


def test_guardrail_passes_placeholders() -> None:
    response = NoBareNumbersGuardrail(FakeLLM()).complete(_writer_request())
    assert "{{fact:f1}}" in response.text


def test_guardrail_blocks_bare_digit_with_446() -> None:
    gateway = NoBareNumbersGuardrail(FakeLLM({"writer": ["bare_digit"]}))
    with pytest.raises(GuardrailViolation) as err:
        gateway.complete(_writer_request())
    assert err.value.status_code == 446


def test_guardrail_ignores_other_nodes() -> None:
    req = LLMRequest(
        node="intake",
        tier="small",
        run_id="r1",
        messages=(Message(role="user", content=json.dumps({"request": "Q3 2026 churn"})),),
    )
    assert json.loads(NoBareNumbersGuardrail(FakeLLM()).complete(req).text)["period"] == "2026-Q3"


def test_fake_llm_counts_and_faults() -> None:
    llm = FakeLLM({"writer": ["invalid_json"]})
    assert not llm.complete(_writer_request()).text.endswith("}")
    assert llm.complete(_writer_request()).text.endswith("}")
    assert llm.calls["writer"] == 2
