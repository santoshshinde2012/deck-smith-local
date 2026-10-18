"""Fill {{fact:id}} placeholders from scalar facts. The renderer, never the writer, formats numbers."""

from __future__ import annotations

import re

from decksmith.domain.errors import GuardrailViolation
from decksmith.domain.facts import FactRegistry, format_value
from decksmith.domain.integrity import FACT_PATTERN


def fill_text(text: str, facts: FactRegistry) -> str:
    """Replace scalar placeholders. A series id in prose is a guardrail failure."""

    def value(match: re.Match[str]) -> str:
        fact = facts.get(match.group(1))
        if fact.kind != "scalar" or fact.value is None:
            raise GuardrailViolation(f"Text placeholder needs a scalar fact: {fact.id}")
        return format_value(fact.value, fact.format, fact.unit)

    return FACT_PATTERN.sub(value, text)
