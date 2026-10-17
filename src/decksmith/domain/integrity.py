"""Numeric integrity by construction: the checks that make 'no invented numbers' testable."""

from __future__ import annotations

import re
from dataclasses import dataclass

from decksmith.domain.deckspec import DeckSpec
from decksmith.domain.facts import FactRegistry

FACT_PATTERN = re.compile(r"\{\{fact:(f[0-9]+)\}\}")
_DIGIT = re.compile(r"[0-9]")


@dataclass(frozen=True)
class Issue:
    slide_id: str
    code: str
    detail: str


def numeric_integrity(spec: DeckSpec, facts: FactRegistry) -> list[Issue]:
    """Every placeholder resolves, no bare digit appears in text, every referenced fact exists."""
    issues: list[Issue] = []
    for slide in spec.slides:
        for text in slide.texts():
            for fact_id in FACT_PATTERN.findall(text):
                if fact_id not in facts:
                    issues.append(Issue(slide.slide_id, "unresolved_fact", fact_id))
            if _DIGIT.search(FACT_PATTERN.sub("", text)):
                issues.append(Issue(slide.slide_id, "bare_digit", text))
        for fact_id in slide.fact_refs():
            if fact_id not in facts:
                issues.append(Issue(slide.slide_id, "unknown_fact_ref", fact_id))
    return issues


def chart_consistency(spec: DeckSpec, facts: FactRegistry) -> list[Issue]:
    """Charts may only plot series facts, and scalars may only appear as KPIs."""
    issues: list[Issue] = []
    for slide in spec.slides:
        if slide.chart:
            for series in slide.chart.series:
                if series.fact_id in facts and facts.get(series.fact_id).kind != "series":
                    issues.append(Issue(slide.slide_id, "chart_needs_series", series.fact_id))
        for kpi in slide.kpis:
            if kpi.fact_id in facts and facts.get(kpi.fact_id).kind != "scalar":
                issues.append(Issue(slide.slide_id, "kpi_needs_scalar", kpi.fact_id))
    return issues


def contains_bare_digit(text: str) -> bool:
    """True when text has a digit outside {{fact:id}} placeholders (the 'no bare numbers' guardrail)."""
    return bool(_DIGIT.search(FACT_PATTERN.sub("", text)))
