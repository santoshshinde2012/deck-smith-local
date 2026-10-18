"""Prompt builders. Versioned here; registered in the MLflow Prompt Registry in production."""

from __future__ import annotations

import json
from typing import Any

from decksmith.domain.deckspec import DeckSpec
from decksmith.domain.outline import Intake, Outline
from decksmith.ports.llm import Message

PROMPT_VERSION = "v4"

INTAKE = """node: intake
Extract deck_type (kpi_review | retention_review | adhoc), audience (exec | team | board), period (e.g. 2026-Q3)
and template_id from the request. Reply with JSON only."""

PLANNER = """node: planner
Propose a deck outline as JSON matching the supplied Outline schema. Choose data questions ONLY from the
listed SQL templates, with parameters as ISO dates. Never write numbers in titles or hints.
One message per slide. Read in order, the title hints are the argument (the titles test). A hint is an
action title: a complete sentence that states the takeaway, not a topic label. The cover names the work.
The sources appendix keeps the hint "Sources".
Choose the layout from the shape of the message: title for the cover, section for a divider, agenda for a
contents list, kpi for headline figures, chart for a trend or a breakdown, bullets for a short argument,
two_content for two groups of points, comparison for a side-by-side, timeline for a sequence, quote for a
line the request itself asks to feature, table for categories against one or more series, summary for
exactly three takeaways, appendix_sources for the source list.
A board audience gets a section divider after the cover. If the request asks for an agenda, a comparison,
a timeline, a quote, a split view, a table or a summary, add that layout before the sources slide.
Include an appendix_sources slide. Keep slide IDs unique and put slides in presentation order."""

WRITER = """node: writer
Write a DeckSpec as JSON matching the supplied schema. Preserve the approved slide IDs, order, layouts,
audience and period; titles may improve. Use the supplied template_id.
Each content slide has one message. Its title is an action title: the takeaway in one sentence. The cover
uses the deck name. The sources appendix is titled Sources. The body of a slide only supports its title.
Never invent quantities, including numbers spelled out in words. In free text, use {{fact:id}} placeholders
for listed scalar facts only. Never write literal digits in titles, subtitles, bullets, KPI labels, chart
series names, column headings, row headings, milestone labels or detail, quotes, attributions or speaker notes.
Series values are for reasoning about direction. Do not copy them into text.
Chart fact_id fields reference series facts; KPI fact_id fields reference scalar facts. A KPI may set
spark_fact_id to a series fact and delta_fact_id to a scalar fact. Combine chart or table series only
when categories, format and unit match exactly.
A comparison slide has exactly two columns. A timeline has milestones in order. A quote slide puts the line
in quote and a short attribution, and does not invent a figure. An agenda lists its entries as bullets.
A summary slide has exactly three bullets. A table names each column's series fact; row labels come from
that series.
Include every referenced fact in the sources list of an appendix_sources slide. Sources contain fact IDs.
Reference checks cannot prove a narrative claim is true."""


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
