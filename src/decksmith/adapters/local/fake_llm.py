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


def _quarter(text: str) -> tuple[int, int]:
    match = re.search(r"Q([1-4])\s*(20[0-9]{2})", text, re.I)
    return (int(match.group(2)), int(match.group(1))) if match else (2026, 3)


def _intake(payload: dict[str, Any], _fault: str) -> str:
    text = payload["request"]
    year, quarter = _quarter(text)
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
            "period": f"{year}-Q{quarter}",
            "template_id": "corp_default@1.0",
        }
    )


def _planner(payload: dict[str, Any], _fault: str) -> str:
    intake = payload["intake"]
    year, quarter = int(intake["period"][:4]), int(intake["period"][-1])
    start = date(year, 3 * quarter - 2, 1)
    end = date(year + (quarter == 4), 1 if quarter == 4 else 3 * quarter + 1, 1)
    window = {"start_month": start.isoformat(), "end_month": end.isoformat()}
    slides: list[dict[str, Any]] = [
        {"slide_id": "s01", "layout": "title", "title_hint": "Retention review", "data_requests": []},
        {
            "slide_id": "s02",
            "layout": "kpi",
            "title_hint": "Headline retention KPIs",
            "data_requests": [
                {"template_id": "churn_rate_quarter", "params": window, "label": "Churn rate"},
                {"template_id": "nrr_quarter", "params": window, "label": "Net revenue retention"},
                {
                    "template_id": "active_subscriptions",
                    "params": {"start_month": start.isoformat()},
                    "label": "Active subscriptions",
                },
            ],
        },
        {
            "slide_id": "s03",
            "layout": "chart",
            "title_hint": "Monthly churn trend",
            "data_requests": [{"template_id": "churn_trend_monthly", "params": window, "label": "Monthly churn"}],
        },
        {
            "slide_id": "s04",
            "layout": "chart",
            "title_hint": "Churn by segment",
            "data_requests": [{"template_id": "churn_by_segment", "params": window, "label": "Churn by segment"}],
        },
        {"slide_id": "s05", "layout": "appendix_sources", "title_hint": "Sources", "data_requests": []},
    ]
    if "segment" in payload.get("feedback", "").lower():
        slides = [s for s in slides if s["slide_id"] != "s04"]
    return json.dumps(
        {
            "deck_title": "Customer retention review",
            "audience": intake["audience"],
            "period": intake["period"],
            "slides": slides,
        }
    )


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
        elif layout == "kpi":
            kpis = [
                {"label": label, "fact_id": by_template[t]}
                for t, label in (
                    ("churn_rate_quarter", "Churn rate"),
                    ("nrr_quarter", "Net revenue retention"),
                    ("active_subscriptions", "Active subscriptions"),
                )
                if t in by_template
            ]
            if not kpis:
                continue
            bullet = (
                "Churn was 18% this quarter"
                if fault == "bare_digit"
                else f"Churn reached {{{{fact:{by_template['churn_rate_quarter']}}}}} this quarter"
                if "churn_rate_quarter" in by_template
                else "Retention held steady"
            )
            if fault == "unknown_fact":
                bullet = "Churn reached {{fact:f99}} this quarter"
            slides.append(
                {
                    "slide_id": sid,
                    "layout": "kpi",
                    "title": "Retention at a glance",
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
            slides.append(
                {
                    "slide_id": sid,
                    "layout": "chart",
                    "title": s["title_hint"],
                    "chart": {
                        "type": kind,
                        "series": [{"name": s["data_requests"][0]["label"], "fact_id": by_template[template]}],
                    },
                    "sources": [by_template[template]],
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
