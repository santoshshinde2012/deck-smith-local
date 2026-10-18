"""Deterministic scorers. Plain functions so CI can call them directly; wrapped for MLflow in harness.py."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from decksmith.domain.deckspec import DeckSpec
from decksmith.domain.facts import FactRegistry
from decksmith.domain.integrity import chart_consistency, numeric_integrity, outline_consistency, source_coverage
from decksmith.domain.outline import Outline


def status_matches(outputs: dict[str, Any], expectations: dict[str, Any]) -> bool:
    return bool(outputs.get("status") == expectations.get("status", "done"))


def fact_integrity(outputs: dict[str, Any], expectations: dict[str, Any]) -> bool:
    """References, chart alignment, sources and approved structure pass deterministic QA."""
    if expectations.get("status", "done") != "done":
        return True
    try:
        spec = DeckSpec.model_validate(outputs.get("spec"))
        facts = FactRegistry.load(outputs.get("facts", []))
        outline = Outline.model_validate(outputs.get("outline"))
    except (ValidationError, TypeError):
        return False
    return not (
        numeric_integrity(spec, facts)
        + chart_consistency(spec, facts)
        + source_coverage(spec)
        + outline_consistency(spec, outline)
    )


def slide_count_in_range(outputs: dict[str, Any], expectations: dict[str, Any]) -> bool:
    if expectations.get("status", "done") != "done":
        return True
    low, high = expectations.get("slides", [1, 25])
    count = (outputs.get("artifact") or {}).get("slide_count", 0)
    return bool(low <= count <= high)


def sources_cited(outputs: dict[str, Any], expectations: dict[str, Any]) -> bool:
    """Every fetched fact is listed in a visible sources appendix."""
    if expectations.get("status", "done") != "done":
        return True
    spec = DeckSpec.model_validate(outputs["spec"])
    cited = {f for s in spec.slides if s.layout == "appendix_sources" for f in s.sources}
    return {f["id"] for f in outputs.get("facts", [])} <= cited


def schema_valid_first_try(outputs: dict[str, Any], expectations: dict[str, Any]) -> bool:
    if expectations.get("status", "done") != "done":
        return True
    return bool(outputs.get("schema_valid_first_try"))


SCORERS = (status_matches, fact_integrity, slide_count_in_range, sources_cited, schema_valid_first_try)
