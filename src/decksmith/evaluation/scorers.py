"""Deterministic scorers. Plain functions so CI can call them directly; wrapped for MLflow in harness.py."""

from __future__ import annotations

from typing import Any

from decksmith.domain.deckspec import DeckSpec
from decksmith.domain.facts import FactRegistry
from decksmith.domain.integrity import numeric_integrity


def status_matches(outputs: dict[str, Any], expectations: dict[str, Any]) -> bool:
    return bool(outputs.get("status") == expectations.get("status", "done"))


def fact_integrity(outputs: dict[str, Any], expectations: dict[str, Any]) -> bool:
    """Every number on every slide resolves to a fact (vacuously true when no deck was expected)."""
    if expectations.get("status", "done") != "done":
        return True
    spec = outputs.get("spec")
    if not spec:
        return False
    return not numeric_integrity(DeckSpec.model_validate(spec), FactRegistry.load(outputs.get("facts", [])))


def slide_count_in_range(outputs: dict[str, Any], expectations: dict[str, Any]) -> bool:
    if expectations.get("status", "done") != "done":
        return True
    low, high = expectations.get("slides", [1, 25])
    count = (outputs.get("artifact") or {}).get("slide_count", 0)
    return bool(low <= count <= high)


def sources_cited(outputs: dict[str, Any], expectations: dict[str, Any]) -> bool:
    """Every fact used is listed on some slide's sources (the appendix lists them all)."""
    if expectations.get("status", "done") != "done":
        return True
    spec = DeckSpec.model_validate(outputs["spec"])
    cited = {f for s in spec.slides for f in s.sources}
    return {f["id"] for f in outputs.get("facts", [])} <= cited


def schema_valid_first_try(outputs: dict[str, Any], expectations: dict[str, Any]) -> bool:
    if expectations.get("status", "done") != "done":
        return True
    return bool(outputs.get("schema_valid_first_try"))


SCORERS = (status_matches, fact_integrity, slide_count_in_range, sources_cited, schema_valid_first_try)
