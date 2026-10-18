"""Prompt builders. Versioned here; registered in the MLflow Prompt Registry in production."""

from __future__ import annotations

import json
from typing import Any

from decksmith.domain.deckspec import DeckSpec
from decksmith.domain.outline import Intake, Outline
from decksmith.ports.llm import Message

PROMPT_VERSION = "v2"

INTAKE = """node: intake
Extract deck_type (kpi_review | retention_review | adhoc), audience (exec | team | board), period (e.g. 2026-Q3)
and template_id from the request. Reply with JSON only."""

PLANNER = """node: planner
Propose a deck outline as JSON matching the supplied Outline schema. Choose data questions ONLY from the
listed SQL templates, with parameters as ISO dates. Never write numbers in titles or hints.
Include an appendix_sources slide. Keep slide IDs unique and put slides in presentation order."""

WRITER = """node: writer
Write a DeckSpec as JSON matching the supplied schema. Preserve the approved slide IDs, order, layouts,
audience and period; titles may improve. Use the supplied template_id.
Never invent quantities, including numbers spelled out in words. In free text, use {{fact:id}} placeholders
for listed scalar facts only. Never write literal digits in titles, subtitles, bullets, KPI labels, chart
series names or speaker notes. Chart fact_id fields reference series facts; KPI fact_id fields reference
scalar facts. Combine chart series only when categories, format and unit match exactly.
Include every referenced fact in the sources list of an appendix_sources slide. Sources contain fact IDs.
Keep titles short and make each one a 'so what'. Reference checks cannot prove a narrative claim is true."""


def _system(instructions: str, schema: dict[str, Any]) -> Message:
    return Message(role="system", content=instructions + "\nJSON Schema:\n" + json.dumps(schema))


def intake_messages(request_text: str) -> tuple[Message, ...]:
    return (
        _system(INTAKE, Intake.model_json_schema()),
        Message(role="user", content=json.dumps({"request": request_text})),
    )


def planner_messages(
    request_text: str, intake: dict[str, Any], templates: list[dict[str, Any]], feedback: str
) -> tuple[Message, ...]:
    payload = {"request": request_text, "intake": intake, "templates": templates, "feedback": feedback}
    return (_system(PLANNER, Outline.model_json_schema()), Message(role="user", content=json.dumps(payload)))


def writer_messages(
    outline: dict[str, Any], facts: list[dict[str, Any]], template_id: str, issues: list[str]
) -> tuple[Message, ...]:
    payload = {"outline": outline, "facts": facts, "template_id": template_id, "fix_issues": issues}
    return (
        _system(WRITER, DeckSpec.model_json_schema()),
        Message(role="user", content=json.dumps(payload, default=str)),
    )
