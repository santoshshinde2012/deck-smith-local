"""Deterministic fake LLM. Lets CI run the whole graph with no keys and no network.

It answers by node (intake, planner, writer) from the JSON payload the prompts send. Faults can be
injected per node to exercise the QA loop and the guardrail: "bare_digit", "invalid_json",
"unknown_fact".
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from typing import Any

from decksmith.domain.composition import layout_for, narrative_roles
from decksmith.ports.llm import LLMRequest, LLMResponse


class FakeLLM:
    def __init__(self, faults: dict[str, list[str]] | None = None) -> None:
        self._faults = {k: list(v) for k, v in (faults or {}).items()}
        self.calls: Counter[str] = Counter()

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls[request.node] += 1
        payload: dict[str, Any] = json.loads(request.messages[-1].content)
        fault = self._faults.get(request.node, []).pop(0) if self._faults.get(request.node) else ""
        handler = {"intake": _intake, "planner": _planner, "writer": _writer}[request.node]
        text = handler(payload, fault)
        model = "fake-strong" if request.tier == "strong" else "fake-small"
        return LLMResponse(
            text=text,
            model=model,
            prompt_tokens=sum(len(m.content) for m in request.messages) // 4,
            completion_tokens=len(text) // 4,
        )


# The seeded lakehouse closes in September. A request that does not name a quarter is the
# published review: the same July–September window, labelled without a year.
_SEEDED_QUARTER = (2026, 3)
_UNNAMED_PERIOD = "Last quarter"


def _named_quarter(text: str) -> tuple[int, int] | None:
    match = re.search(r"Q([1-4])\s*(20[0-9]{2})", text, re.I)
    if match is None:
        return None
    return int(match.group(2)), int(match.group(1))


def _quarter_of(period: str) -> tuple[int, int]:
    match = re.fullmatch(r"(20[0-9]{2})-Q([1-4])", period)
    if match is None:
        return _SEEDED_QUARTER
    return int(match.group(1)), int(match.group(2))


def _intake(payload: dict[str, Any], _fault: str) -> str:
    text = payload["request"]
    named = _named_quarter(text)
    deck_type = "retention_review" if re.search(r"churn|retention", text, re.I) else "kpi_review"
    audience = (
        "board"
        if "board" in text.lower()
        else "team"
        if "team" in text.lower() and "exec" not in text.lower()
        else "exec"
    )
    return json.dumps(
        {
            "deck_type": deck_type,
            "audience": audience,
            "period": f"{named[0]}-Q{named[1]}" if named else _UNNAMED_PERIOD,
            "template_id": "corp_default@1.0",
        }
    )


_HINTS = {
    "cover": "Retention review",
    "divider": "The retention picture",
    "scorecard": "Headline retention KPIs",
    "trend": "The monthly path of churn",
    "breakdown": "Churn across segments",
    "agenda": "What this review covers",
    "comparison": "Two ways to read retention",
    "timeline": "How the review is sequenced",
    "quote": "The point of the review",
    "table": "Where churn sits by segment",
    "summary": "Three readings of retention",
    "split": "The story in two parts",
    "narrative": "What the figures support",
    "sources": "Sources",
}


def _planner(payload: dict[str, Any], _fault: str) -> str:
    intake = payload["intake"]
    year, quarter = _quarter_of(str(intake["period"]))
    start = date(year, 3 * quarter - 2, 1)
    end = date(year + (quarter == 4), 1 if quarter == 4 else 3 * quarter + 1, 1)
    window = {"start_month": start.isoformat(), "end_month": end.isoformat()}
    roles = narrative_roles(intake["audience"], payload.get("request", ""))
    slides = [_planned_slide(role, index, window, start) for index, role in enumerate(roles, start=1)]
    if "segment" in payload.get("feedback", "").lower():
        slides = [slide for slide in slides if slide.get("role") != "breakdown"]
    for slide in slides:
        slide.pop("role", None)
    return json.dumps(
        {
            "deck_title": "Customer retention review",
            "audience": intake["audience"],
            "period": intake["period"],
            "slides": slides,
        }
    )


def _planned_slide(role: str, index: int, window: dict[str, str], start: date) -> dict[str, Any]:
    requests: list[dict[str, Any]] = []
    if role == "scorecard":
        requests = [
            {"template_id": "churn_rate_quarter", "params": window, "label": "Monthly churn (weighted)"},
            {"template_id": "nrr_quarter", "params": window, "label": "Monthly NRR (weighted)"},
            {
                "template_id": "active_subscriptions",
                "params": {"start_month": start.isoformat()},
                "label": "Active subscriptions",
            },
        ]
    elif role == "trend":
        requests = [{"template_id": "churn_trend_monthly", "params": window, "label": "Monthly churn"}]
    elif role == "breakdown":
        requests = [{"template_id": "churn_by_segment", "params": window, "label": "Weighted monthly churn by segment"}]
    return {
        "slide_id": f"s{index:02d}",
        "layout": layout_for(role),
        "title_hint": _HINTS[role],
        "data_requests": requests,
        "role": role,
    }


def _writer(payload: dict[str, Any], fault: str) -> str:
    if fault == "invalid_json":
        return '{"spec_version": "1.0", "slides": ['
    by_template = {f["template_id"]: f["id"] for f in payload["facts"]}
    all_ids = [f["id"] for f in payload["facts"]]
    outline = payload["outline"]
    slides: list[dict[str, Any]] = []
    for s in outline["slides"]:
        sid, layout = s["slide_id"], s["layout"]
        if layout == "title":
            slides.append(
                {
                    "slide_id": sid,
                    "layout": "title",
                    "title": outline["deck_title"],
                    "subtitle": f"Prepared for the {outline['audience']} audience",
                }
            )
        elif layout == "section":
            slides.append(
                {
                    "slide_id": sid,
                    "layout": "section",
                    "title": s["title_hint"],
                    "subtitle": f"For the {outline['audience']} audience",
                }
            )
        elif layout == "kpi":
            kpis = [
                {"label": label, "fact_id": by_template[t]}
                for t, label in (
                    ("churn_rate_quarter", "Monthly churn (weighted)"),
                    ("nrr_quarter", "Monthly NRR (weighted)"),
                    ("active_subscriptions", "Active subscriptions"),
                )
                if t in by_template
            ]
            if not kpis:
                continue
            if "churn_trend_monthly" in by_template and "churn_rate_quarter" in by_template:
                for kpi in kpis:
                    if kpi["fact_id"] == by_template["churn_rate_quarter"]:
                        kpi["spark_fact_id"] = by_template["churn_trend_monthly"]
            bullet = (
                "Churn was 18% this quarter"
                if fault == "bare_digit"
                else (
                    f"Weighted monthly churn was {{{{fact:{by_template['churn_rate_quarter']}}}}} "
                    "over the review period"
                )
                if "churn_rate_quarter" in by_template
                else "Retention held steady"
            )
            if fault == "unknown_fact":
                bullet = "Churn reached {{fact:f99}} this quarter"
            slides.append(
                {
                    "slide_id": sid,
                    "layout": "kpi",
                    "title": "Where retention stands",
                    "kpis": kpis,
                    "bullets": [bullet],
                    "sources": [k["fact_id"] for k in kpis],
                }
            )
        elif layout == "chart":
            template = s["data_requests"][0]["template_id"]
            if template not in by_template:
                continue
            kind = "line" if "trend" in template else "bar"
            fact = _fact(payload["facts"], template)
            title = _trend_title(fact) if "trend" in template else _breakdown_title(fact, s["title_hint"])
            slides.append(
                {
                    "slide_id": sid,
                    "layout": "chart",
                    "title": title,
                    "chart": {
                        "type": kind,
                        "series": [{"name": s["data_requests"][0]["label"], "fact_id": by_template[template]}],
                    },
                    "sources": [by_template[template]],
                }
            )
        elif layout == "agenda":
            slides.append(
                {
                    "slide_id": sid,
                    "layout": "agenda",
                    "title": s["title_hint"],
                    "bullets": ["The headline figures", "The monthly path", "The segment split", "The sources"],
                }
            )
        elif layout == "bullets":
            slides.append(
                {
                    "slide_id": sid,
                    "layout": "bullets",
                    "title": s["title_hint"],
                    "bullets": ["Read the headline figures first", "Then the monthly path", "Then the segment split"],
                }
            )
        elif layout == "two_content":
            slides.append(
                {
                    "slide_id": sid,
                    "layout": "two_content",
                    "title": s["title_hint"],
                    "bullets": [
                        "The monthly path shows the shape",
                        "The segment split shows where it sits",
                        "The headline figures frame both",
                        "The sources trace every figure",
                    ],
                }
            )
        elif layout == "comparison":
            slides.append(
                {
                    "slide_id": sid,
                    "layout": "comparison",
                    "title": s["title_hint"],
                    "columns": [
                        {"heading": "The rate", "bullets": ["Weighted monthly churn", "Shows who left"]},
                        {"heading": "The base", "bullets": ["Active subscriptions", "Shows who remains"]},
                    ],
                }
            )
        elif layout == "timeline":
            slides.append(
                {
                    "slide_id": sid,
                    "layout": "timeline",
                    "title": s["title_hint"],
                    "milestones": [
                        {"label": "Headline", "detail": "The figures that frame the review"},
                        {"label": "Trend", "detail": "The monthly path"},
                        {"label": "Segments", "detail": "Where churn sits"},
                        {"label": "Sources", "detail": "How to trace a figure"},
                    ],
                }
            )
        elif layout == "table":
            template = "churn_by_segment" if "churn_by_segment" in by_template else ""
            if not template:
                continue
            slides.append(
                {
                    "slide_id": sid,
                    "layout": "table",
                    "title": _breakdown_title(_fact(payload["facts"], template), s["title_hint"]),
                    "table": {
                        "row_heading": "Segment",
                        "columns": [{"heading": "Weighted churn", "fact_id": by_template[template]}],
                    },
                    "sources": [by_template[template]],
                }
            )
        elif layout == "summary":
            slides.append(
                {
                    "slide_id": sid,
                    "layout": "summary",
                    "title": s["title_hint"],
                    "bullets": [
                        "The headline figures frame the review",
                        "The monthly path shows the direction",
                        "The segment split shows where it sits",
                    ],
                }
            )
        elif layout == "quote":
            slides.append(
                {
                    "slide_id": sid,
                    "layout": "quote",
                    "title": s["title_hint"],
                    "quote": "A retention review is a story about who stays.",
                    "attribution": "Review note",
                }
            )
        elif layout == "appendix_sources":
            slides.append({"slide_id": sid, "layout": "appendix_sources", "title": "Sources", "sources": all_ids})
    return json.dumps(
        {
            "spec_version": "1.0",
            "template_id": payload["template_id"],
            "title": outline["deck_title"],
            "audience": outline["audience"],
            "period": outline["period"],
            "slides": slides,
        }
    )


def _fact(facts: list[dict[str, Any]], template: str) -> dict[str, Any]:
    for fact in facts:
        if fact.get("template_id") == template:
            return fact
    return {}


def _trend_title(fact: dict[str, Any]) -> str:
    values = fact.get("values") or []
    if len(values) < 2:
        return "The monthly path of churn"
    if values[-1] < values[0]:
        return "Monthly churn ended lower than it started"
    if values[-1] > values[0]:
        return "Monthly churn ended higher than it started"
    return "Monthly churn ended where it started"


def _breakdown_title(fact: dict[str, Any], fallback: str) -> str:
    categories = list(fact.get("categories") or [])
    values = list(fact.get("values") or [])
    if not categories or len(categories) != len(values):
        return fallback
    peak = str(categories[max(range(len(values)), key=lambda index: (values[index], -index))])
    if any(character.isdigit() for character in peak):
        return "Churn is uneven across segments"
    return f"Churn is highest in {peak}"
