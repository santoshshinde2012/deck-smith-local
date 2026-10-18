"""Deterministic reference, digit and chart checks, not a proof of narrative truth."""

from __future__ import annotations

from dataclasses import dataclass

from decksmith.domain.deckspec import FACT_PATTERN as FACT_PATTERN
from decksmith.domain.deckspec import DeckSpec
from decksmith.domain.facts import FactRegistry
from decksmith.domain.outline import Outline


@dataclass(frozen=True)
class Issue:
    slide_id: str
    code: str
    detail: str


def numeric_integrity(spec: DeckSpec, facts: FactRegistry) -> list[Issue]:
    """Every text placeholder is scalar, every reference resolves, no bare digit appears.

    Spelled-out quantities and the meaning of a claim still require review.
    """
    issues: list[Issue] = []
    issues.extend(_text_issues("deck", spec.title, facts))
    for slide in spec.slides:
        for text in slide.texts():
            issues.extend(_text_issues(slide.slide_id, text, facts))
        for fact_id in slide.fact_refs():
            if fact_id not in facts:
                issues.append(Issue(slide.slide_id, "unknown_fact_ref", fact_id))
    return issues


def _text_issues(slide_id: str, text: str, facts: FactRegistry) -> list[Issue]:
    issues: list[Issue] = []
    for fact_id in FACT_PATTERN.findall(text):
        if fact_id not in facts:
            issues.append(Issue(slide_id, "unresolved_fact", fact_id))
        elif facts.get(fact_id).kind != "scalar":
            issues.append(Issue(slide_id, "placeholder_needs_scalar", fact_id))
    remaining = FACT_PATTERN.sub("", text)
    if "{{fact:" in remaining:
        issues.append(Issue(slide_id, "invalid_fact_placeholder", text))
    if contains_bare_digit(text):
        issues.append(Issue(slide_id, "bare_digit", text))
    return issues


def chart_consistency(spec: DeckSpec, facts: FactRegistry) -> list[Issue]:
    """Charts share categories, formats and units; KPIs use scalars."""
    issues: list[Issue] = []
    for slide in spec.slides:
        if slide.chart:
            plotted = []
            for series in slide.chart.series:
                if series.fact_id not in facts:
                    continue  # numeric_integrity reports unknown references
                fact = facts.get(series.fact_id)
                if fact.kind != "series":
                    issues.append(Issue(slide.slide_id, "chart_needs_series", series.fact_id))
                else:
                    plotted.append(fact)
            if plotted:
                first = plotted[0]
                for fact in plotted[1:]:
                    if fact.categories != first.categories:
                        issues.append(Issue(slide.slide_id, "chart_category_mismatch", fact.id))
                    if (fact.format, fact.unit) != (first.format, first.unit):
                        issues.append(Issue(slide.slide_id, "chart_format_mismatch", fact.id))
        for kpi in slide.kpis:
            if kpi.fact_id in facts and facts.get(kpi.fact_id).kind != "scalar":
                issues.append(Issue(slide.slide_id, "kpi_needs_scalar", kpi.fact_id))
    return issues


def source_coverage(spec: DeckSpec) -> list[Issue]:
    """Every used fact has a visible source entry in a sources appendix."""
    appendices = [slide for slide in spec.slides if slide.layout == "appendix_sources"]
    if not appendices:
        return [Issue("deck", "missing_sources_appendix", "include an appendix_sources slide")]
    cited = {fact_id for slide in appendices for fact_id in slide.sources}
    referenced = set(FACT_PATTERN.findall(spec.title))
    for slide in spec.slides:
        referenced.update(slide.fact_refs())
    return [Issue("deck", "missing_source", fact_id) for fact_id in sorted(referenced - cited)]


def outline_consistency(spec: DeckSpec, outline: Outline) -> list[Issue]:
    """Preserve the approved slide order/layouts and audience/period; titles may improve."""
    issues: list[Issue] = []
    approved = [(slide.slide_id, slide.layout) for slide in outline.slides]
    actual = [(slide.slide_id, slide.layout) for slide in spec.slides]
    if actual != approved:
        issues.append(Issue("deck", "outline_mismatch", f"expected slide IDs/layouts {approved}"))
    if spec.audience != outline.audience:
        issues.append(Issue("deck", "audience_mismatch", outline.audience))
    if spec.period != outline.period:
        issues.append(Issue("deck", "period_mismatch", outline.period))
    return issues


def contains_bare_digit(text: str) -> bool:
    """True when text has a digit outside {{fact:id}} placeholders (the 'no bare numbers' guardrail)."""
    return any(char.isdigit() for char in FACT_PATTERN.sub("", text))
