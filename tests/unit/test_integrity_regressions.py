import json

import pytest
from pydantic import ValidationError

from decksmith.application.guardrails import _has_bare_number
from decksmith.application.prompts import intake_messages, planner_messages, writer_messages
from decksmith.domain.deckspec import DeckSpec
from decksmith.domain.facts import FactRegistry
from decksmith.domain.integrity import chart_consistency, numeric_integrity, outline_consistency, source_coverage
from decksmith.domain.outline import Outline


@pytest.mark.parametrize("field", ["title", "subtitle", "bullets", "label", "name", "notes"])
def test_guardrail_checks_every_writer_text_field(field: str) -> None:
    assert _has_bare_number(json.dumps({field: ["Invented 99%"] if field == "bullets" else "Invented 99%"}))
    assert not _has_bare_number(json.dumps({field: "Observed {{fact:f1}}"}))


@pytest.mark.parametrize("field", ["notes", "series_name", "deck_title"])
def test_finished_spec_checks_notes_names_and_metadata(
    spec_dict: dict[str, object], facts: FactRegistry, field: str
) -> None:
    spec = DeckSpec.model_validate(spec_dict)
    if field == "notes":
        spec.slides[2].notes = "Invented 99%"
    elif field == "series_name":
        assert spec.slides[2].chart is not None
        spec.slides[2].chart.series[0].name = "Invented 99%"
    else:
        spec.title = "Invented 99%"
    assert "bare_digit" in {issue.code for issue in numeric_integrity(spec, facts)}


def test_series_text_placeholder_is_not_a_scalar(spec_dict: dict[str, object], facts: FactRegistry) -> None:
    spec = DeckSpec.model_validate(spec_dict)
    spec.slides[3].bullets = ["Quarter churn {{fact:f3}}"]
    assert "placeholder_needs_scalar" in {issue.code for issue in numeric_integrity(spec, facts)}


def test_malformed_placeholder_is_rejected(spec_dict: dict[str, object], facts: FactRegistry) -> None:
    spec = DeckSpec.model_validate(spec_dict)
    spec.slides[3].bullets = ["Churn {{fact:missing}}"]
    assert "invalid_fact_placeholder" in {issue.code for issue in numeric_integrity(spec, facts)}


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"categories": ("Enterprise", "Mid-market", "SMB")}, "chart_category_mismatch"),
        ({"categories": ("2026-09", "2026-08", "2026-07")}, "chart_category_mismatch"),
        ({"format": "int"}, "chart_format_mismatch"),
        ({"unit": "USD"}, "chart_format_mismatch"),
    ],
)
def test_charts_require_matching_category_order_and_measure(
    spec_dict: dict[str, object], facts: FactRegistry, changes: dict[str, object], code: str
) -> None:
    spec = DeckSpec.model_validate(spec_dict)
    other = facts.get("f3").model_copy(update={"id": "f4", **changes})
    facts.add(other)
    assert spec.slides[2].chart is not None
    spec.slides[2].chart.series.append(spec.slides[2].chart.series[0].model_copy(update={"fact_id": "f4"}))
    assert code in {issue.code for issue in chart_consistency(spec, facts)}


def test_text_references_are_inferred_and_require_visible_sources(spec_dict: dict[str, object]) -> None:
    spec = DeckSpec.model_validate(spec_dict)
    spec.slides[3].bullets = ["Churn reached {{fact:f1}}"]
    spec.slides[3].notes = "There are {{fact:f2}} active subscriptions"
    assert spec.slides[3].fact_refs() == {"f1", "f2"}
    spec.slides[-1].sources.remove("f1")
    assert [(issue.code, issue.detail) for issue in source_coverage(spec)] == [("missing_source", "f1")]
    spec.slides.pop()
    assert source_coverage(spec)[0].code == "missing_sources_appendix"


def test_approved_structure_preserves_order_layout_audience_and_period(spec_dict: dict[str, object]) -> None:
    spec = DeckSpec.model_validate(spec_dict)
    outline = Outline(
        deck_title=spec.title,
        audience=spec.audience,
        period=spec.period,
        slides=[
            {"slide_id": slide.slide_id, "layout": slide.layout, "title_hint": slide.title} for slide in spec.slides
        ],
    )
    spec.slides[0].title = "A clearer headline"
    assert outline_consistency(spec, outline) == []
    spec.slides.reverse()
    spec.audience = "board"
    spec.period = "2026-Q4"
    assert {issue.code for issue in outline_consistency(spec, outline)} == {
        "outline_mismatch",
        "audience_mismatch",
        "period_mismatch",
    }


def test_all_model_prompts_supply_the_actual_json_schema() -> None:
    messages = [
        intake_messages("A retention review"),
        planner_messages("A retention review", {}, [], ""),
        writer_messages({}, [], "corp_default@1.0", []),
    ]
    for prompt, expected in zip(messages, ["Intake", "Outline", "DeckSpec"], strict=True):
        schema = json.loads(prompt[0].content.split("JSON Schema:\n", 1)[1])
        assert schema["title"] == expected
        assert schema["additionalProperties"] is False


def test_schema_refuses_unimplemented_tables_and_kpi_deltas(spec_dict: dict[str, object]) -> None:
    spec = DeckSpec.model_validate(spec_dict)
    payload = spec.model_dump()
    payload["slides"][3]["layout"] = "table"
    with pytest.raises(ValidationError, match="layout"):
        DeckSpec.model_validate(payload)
    payload = spec.model_dump()
    payload["slides"][1]["kpis"][0]["delta_fact_id"] = "f2"
    with pytest.raises(ValidationError, match="delta_fact_id"):
        DeckSpec.model_validate(payload)
    schema = DeckSpec.model_json_schema()
    assert "table" not in schema["$defs"]["Slide"]["properties"]["layout"]["enum"]
    assert "delta_fact_id" not in schema["$defs"]["Kpi"]["properties"]


@pytest.mark.parametrize("field", ["subtitle", "bullets", "kpis", "chart"])
def test_schema_rejects_content_the_selected_layout_cannot_render(spec_dict: dict[str, object], field: str) -> None:
    spec = DeckSpec.model_validate(spec_dict)
    payload = spec.model_dump()
    section = payload["slides"][0]
    if field == "subtitle":
        section["layout"] = "bullets"
    elif field == "bullets":
        section["bullets"] = ["This would disappear"]
    elif field == "kpis":
        section["kpis"] = payload["slides"][1]["kpis"]
    else:
        section["chart"] = payload["slides"][2]["chart"]
    with pytest.raises(ValidationError, match=field):
        DeckSpec.model_validate(payload)
