"""Compact, credential-free payloads for trace spans.

The tracer adapter truncates and strips secret-shaped keys again. These helpers choose which
fields are worth recording: the request, the acting user, outlines, specs and facts the user
is allowed to see. They leave out tokens, SQL text, filesystem paths and query timestamps.
"""

from __future__ import annotations

from typing import Any

from decksmith.domain.facts import FactFormat, format_value

_FORMATS: frozenset[FactFormat] = frozenset(("pct1", "int", "currency0", "decimal2"))


def outline_record(outline: dict[str, Any] | None) -> dict[str, Any] | None:
    if not outline:
        return None
    slides = list(outline.get("slides") or [])
    return {
        "deck_title": outline.get("deck_title"),
        "audience": outline.get("audience"),
        "period": outline.get("period"),
        "slide_count": len(slides),
        "slides": [
            {"slide_id": slide.get("slide_id"), "layout": slide.get("layout"), "title_hint": slide.get("title_hint")}
            for slide in slides[:15]
        ],
    }


def spec_record(spec: dict[str, Any] | None) -> dict[str, Any] | None:
    if not spec:
        return None
    slides = list(spec.get("slides") or [])
    return {
        "title": spec.get("title"),
        "audience": spec.get("audience"),
        "period": spec.get("period"),
        "slide_count": len(slides),
        "slides": [
            {"slide_id": slide.get("slide_id"), "layout": slide.get("layout"), "title": slide.get("title")}
            for slide in slides[:15]
        ],
    }


def fact_record(fact: dict[str, Any]) -> dict[str, Any]:
    raw_source = fact.get("source")
    source: dict[str, Any] = raw_source if isinstance(raw_source, dict) else {}
    record: dict[str, Any] = {
        "id": fact.get("id"),
        "label": fact.get("label"),
        "kind": fact.get("kind"),
        "template_id": source.get("template_id"),
    }
    if fact.get("kind") == "scalar" and fact.get("value") is not None:
        record["display"] = format_value(
            float(fact["value"]), _as_format(fact.get("format")), str(fact.get("unit") or "")
        )
    else:
        categories = list(fact.get("categories") or [])
        record["categories"] = [str(category) for category in categories[:12]]
        record["points"] = len(list(fact.get("values") or []))
    return record


def fact_records(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [fact_record(fact) for fact in facts[:20]]


def message_records(messages: tuple[Any, ...] | list[Any]) -> list[dict[str, str]]:
    return [{"role": str(message.role), "content": str(message.content)} for message in messages]


def invocation_output(view: Any) -> dict[str, Any]:
    """Summary of a finished graph invocation: outline, deck, or the refusal."""
    payload: dict[str, Any] = {"run_id": view.run_id, "status": view.status}
    outline = outline_record(view.outline)
    if outline is not None:
        payload["outline"] = outline
    spec = spec_record(view.spec)
    if spec is not None:
        payload["spec"] = spec
    artifact = view.artifact or None
    if artifact:
        payload["deck"] = {
            "slide_count": artifact.get("slide_count"),
            "sha256": str(artifact.get("sha256", ""))[:12],
        }
    if view.error:
        payload["error"] = view.error
    if view.issues:
        payload["issues"] = list(view.issues)[:8]
    return payload


def _as_format(fmt: object) -> FactFormat:
    if isinstance(fmt, str) and fmt in _FORMATS:
        return fmt
    return "decimal2"
