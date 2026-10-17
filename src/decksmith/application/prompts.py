"""Prompt builders. Versioned here; registered in the MLflow Prompt Registry in production."""

from __future__ import annotations

import json
from typing import Any

from decksmith.ports.llm import Message

PROMPT_VERSION = "v1"

INTAKE = """node: intake
Extract deck_type (kpi_review | retention_review | adhoc), audience (exec | team | board), period (e.g. 2026-Q3)
and template_id from the request. Reply with JSON only."""

PLANNER = """node: planner
Propose a deck outline as JSON matching the Outline schema. One data question per slide, chosen ONLY from the
listed SQL templates, with parameters as ISO dates. Never write numbers in titles or hints."""

WRITER = """node: writer
Write a DeckSpec as JSON. Every number MUST appear only as a {{fact:id}} placeholder for a listed fact.
Never write digits anywhere else in titles, subtitles, bullets or labels. Charts reference series facts;
KPIs reference scalar facts. Keep titles short and make each one a 'so what'."""


def intake_messages(request_text: str) -> tuple[Message, ...]:
    return (Message(role="system", content=INTAKE), Message(role="user", content=json.dumps({"request": request_text})))


def planner_messages(
    request_text: str, intake: dict[str, Any], templates: list[dict[str, Any]], feedback: str
) -> tuple[Message, ...]:
    payload = {"request": request_text, "intake": intake, "templates": templates, "feedback": feedback}
    return (Message(role="system", content=PLANNER), Message(role="user", content=json.dumps(payload)))


def writer_messages(
    outline: dict[str, Any], facts: list[dict[str, Any]], template_id: str, issues: list[str]
) -> tuple[Message, ...]:
    payload = {"outline": outline, "facts": facts, "template_id": template_id, "fix_issues": issues}
    return (Message(role="system", content=WRITER), Message(role="user", content=json.dumps(payload, default=str)))
