"""Narrative roles the planner maps onto slide layouts.

The cover names the work. Every later slide carries one message. The sources slide is an appendix.
Board reviews open with a section divider. An explicit ask in the request adds the matching layout.
"""

from __future__ import annotations

from decksmith.domain.deckspec import Layout

ROLE_TO_LAYOUT: dict[str, Layout] = {
    "cover": "title",
    "divider": "section",
    "agenda": "agenda",
    "scorecard": "kpi",
    "trend": "chart",
    "breakdown": "chart",
    "narrative": "bullets",
    "split": "two_content",
    "comparison": "comparison",
    "timeline": "timeline",
    "quote": "quote",
    "table": "table",
    "summary": "summary",
    "sources": "appendix_sources",
}


def layout_for(role: str) -> Layout:
    """Return the slide layout that renders one narrative role."""
    try:
        return ROLE_TO_LAYOUT[role]
    except KeyError:
        raise ValueError(f"unknown narrative role: {role}") from None


def narrative_roles(audience: str, request: str) -> tuple[str, ...]:
    """Choose an ordered story from the audience and the wording of the request.

    The canonical retention review is cover, scorecard, trend, breakdown, sources.
    """
    body: list[str] = ["scorecard", "trend", "breakdown"]
    if audience == "board":
        body.insert(0, "divider")
    text = f" {request.lower()} "
    extras: list[str] = []
    if "agenda" in text:
        extras.append("agenda")
    if any(token in text for token in ("compare", "comparison", "versus", " vs ")):
        extras.append("comparison")
    if "timeline" in text or "roadmap" in text:
        extras.append("timeline")
    if "quote" in text:
        extras.append("quote")
    if "two column" in text or "two-column" in text or "split view" in text:
        extras.append("split")
    if " table" in text or "matrix" in text:
        extras.append("table")
    if "summary" in text or "takeaway" in text:
        extras.append("summary")
    return ("cover", *body, *extras, "sources")
