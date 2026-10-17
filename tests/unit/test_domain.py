import pytest
from pydantic import ValidationError

from decksmith.domain.deckspec import DeckSpec
from decksmith.domain.facts import Fact, FactRegistry, format_value
from decksmith.domain.integrity import chart_consistency, contains_bare_digit, numeric_integrity
from decksmith.domain.outline import Outline


def test_format_value() -> None:
    assert format_value(0.0236, "pct1") == "2.4%"
    assert format_value(6172, "int") == "6,172"
    assert format_value(1234.5, "currency0", "EUR") == "€1,234"
    assert format_value(1.5, "decimal2") == "1.50"


def test_registry_ids_and_roundtrip(facts: FactRegistry) -> None:
    assert facts.next_id() == "f4"
    assert "f1" in facts and "f9" not in facts
    assert FactRegistry.load(facts.dump()).dump() == facts.dump()
    with pytest.raises(ValueError):
        facts.add(facts.get("f1"))


def test_fact_shape_validation(facts: FactRegistry) -> None:
    src = facts.get("f1").source
    with pytest.raises(ValidationError):
        Fact(id="f9", kind="scalar", label="x", source=src)
    with pytest.raises(ValidationError):
        Fact(id="f9", kind="series", label="x", categories=("a",), values=(), source=src)


def test_deckspec_valid(spec_dict: dict[str, object]) -> None:
    spec = DeckSpec.model_validate(spec_dict)
    assert spec.slides[1].fact_refs() == {"f1", "f2"}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["slides"].append(dict(d["slides"][0])),  # duplicate slide id
        lambda d: d["slides"][1].update(kpis=[]),  # kpi layout without kpis
        lambda d: d["slides"][2].update(chart=None),  # chart layout without chart
        lambda d: d["slides"][3].update(bullets=["x"] * 7),  # more than six bullets
        lambda d: d["slides"][3].update(bullets=["x" * 161]),  # bullet too long
        lambda d: d.update(template_id="Corp Default"),  # bad template id
        lambda d: d["slides"][0].update(colour="red"),  # closed objects
    ],
)
def test_deckspec_rejects(spec_dict: dict[str, object], mutate) -> None:  # type: ignore[no-untyped-def]
    mutate(spec_dict)
    with pytest.raises(ValidationError):
        DeckSpec.model_validate(spec_dict)


def test_numeric_integrity_clean(spec_dict: dict[str, object], facts: FactRegistry) -> None:
    spec = DeckSpec.model_validate(spec_dict)
    assert numeric_integrity(spec, facts) == []
    assert chart_consistency(spec, facts) == []


def test_numeric_integrity_catches(spec_dict: dict[str, object], facts: FactRegistry) -> None:
    spec_dict["slides"][3]["bullets"] = ["Churn fell 18% in Q3", "See {{fact:f42}}"]  # type: ignore[index]
    codes = {i.code for i in numeric_integrity(DeckSpec.model_validate(spec_dict), facts)}
    assert {"bare_digit", "unresolved_fact"} <= codes


def test_chart_needs_series_fact(spec_dict: dict[str, object], facts: FactRegistry) -> None:
    spec_dict["slides"][2]["chart"]["series"][0]["fact_id"] = "f1"  # type: ignore[index]
    assert chart_consistency(DeckSpec.model_validate(spec_dict), facts)


def test_bare_digit_ignores_placeholders() -> None:
    assert not contains_bare_digit("Churn {{fact:f12}} this quarter")
    assert contains_bare_digit("Q3 churn")


def test_outline_bounds() -> None:
    with pytest.raises(ValidationError):
        Outline.model_validate({"deck_title": "x", "audience": "exec", "period": "2026-Q3", "slides": []})
