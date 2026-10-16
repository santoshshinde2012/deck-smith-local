from pathlib import Path

from pptx import Presentation

from decksmith.adapters.local.pptx_renderer import PptxRenderer
from decksmith.domain.deckspec import DeckSpec
from decksmith.domain.facts import FactRegistry


def test_renders_native_objects(renderer: PptxRenderer, spec_dict: dict[str, object], facts: FactRegistry) -> None:
    deck = renderer.render(DeckSpec.model_validate(spec_dict), facts, "run1")
    prs = Presentation(deck.path)
    assert deck.slide_count == len(prs.slides) == 5
    texts = [sh.text_frame.text for s in prs.slides for sh in s.shapes if sh.has_text_frame]
    assert any("2.4%" in t for t in texts) and any("6,172" in t for t in texts)
    assert not any("{{fact" in t for t in texts)
    charts = [sh.chart for s in prs.slides for sh in s.shapes if sh.has_chart]
    assert len(charts) == 1 and list(charts[0].plots[0].categories) == ["2026-07", "2026-08", "2026-09"]
    assert prs.core_properties.subject == "run_id=run1"
    assert "f3" in prs.slides[2].notes_slide.notes_text_frame.text  # provenance in speaker notes


def test_content_hash_is_stable(tmp_path: Path, spec_dict: dict[str, object], facts: FactRegistry) -> None:
    spec = DeckSpec.model_validate(spec_dict)
    a = PptxRenderer(tmp_path / "a").render(spec, facts, "same")
    b = PptxRenderer(tmp_path / "b").render(spec, facts, "same")
    assert a.content_hash == b.content_hash


def test_overflow_flagged(renderer: PptxRenderer, spec_dict: dict[str, object], facts: FactRegistry) -> None:
    spec_dict["slides"][3]["bullets"] = ["word " * 30] * 6  # type: ignore[index]
    deck = renderer.render(DeckSpec.model_validate(spec_dict), facts, "run2")
    assert deck.overflow_slides == ("s04",)
