"""Deterministic python-pptx renderer: native, editable charts and text; numbers formatted from facts.

Same spec + same theme => same slide XML (checked by content_hash), so golden tests work in CI.
Layouts are painters in a registry. The blank Office layout is only a canvas; the grid, type and
colour come from the theme.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime
from pathlib import Path

from pptx import Presentation
from pptx.presentation import Presentation as PresentationDocument
from pptx.slide import SlideLayout
from pptx.util import Emu, Length

from decksmith.adapters.local.design.canvas import Canvas
from decksmith.adapters.local.design.layouts import LayoutRegistry, default_registry
from decksmith.adapters.local.design.text import fill_text
from decksmith.adapters.local.design.theme import get_theme
from decksmith.domain.deckspec import DeckSpec, Slide
from decksmith.domain.errors import GuardrailViolation
from decksmith.domain.facts import Fact, FactRegistry
from decksmith.domain.integrity import chart_consistency, numeric_integrity, source_coverage
from decksmith.ports.renderer import RenderedDeck

# Exact 16:9 widescreen: 13.333... in by 7.5 in.
WIDESCREEN = (Emu(12192000), Emu(6858000))
FIXED_TIMESTAMP = datetime(2026, 1, 1)


class PptxRenderer:
    def __init__(
        self,
        output_dir: Path,
        template_path: Path | None = None,
        theme: str = "meridian",
        registry: LayoutRegistry | None = None,
    ) -> None:
        self._out = output_dir
        self._template = template_path
        self._theme = get_theme(theme)
        self._registry = registry or default_registry()

    def render(self, spec: DeckSpec, facts: FactRegistry, run_id: str) -> RenderedDeck:
        issues = numeric_integrity(spec, facts) + chart_consistency(spec, facts) + source_coverage(spec)
        if issues:
            raise GuardrailViolation("Invalid deck: " + "; ".join(f"{i.code}: {i.detail}" for i in issues))
        prs = Presentation()
        width, height = _slide_size(self._template)
        prs.slide_width, prs.slide_height = width, height
        blank = _blank(prs)
        canvas = Canvas(int(width), int(height))
        overflow: list[str] = []
        for index, slide_spec in enumerate(spec.slides, start=1):
            slide = prs.slides.add_slide(blank)
            if self._registry.paint(slide, slide_spec, facts, self._theme, canvas, index):
                overflow.append(slide_spec.slide_id)
            slide.notes_slide.notes_text_frame.text = _notes(slide_spec, facts)
        props = prs.core_properties
        props.title, props.subject, props.keywords = fill_text(spec.title, facts), f"run_id={run_id}", spec.template_id
        props.author, props.category, props.revision = "DeckSmith", self._theme.id, 1
        props.created = props.modified = FIXED_TIMESTAMP
        self._out.mkdir(parents=True, exist_ok=True)
        path = self._out / f"{run_id}.pptx"
        prs.save(str(path))
        return RenderedDeck(
            path=str(path),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            content_hash=content_hash(path),
            slide_count=len(spec.slides),
            overflow_slides=tuple(overflow),
        )


def content_hash(path: Path) -> str:
    """Hash of slide, chart and notes XML: ignores zip timestamps and embedded chart workbooks."""
    digest = hashlib.sha256()
    with zipfile.ZipFile(path) as zipped:
        for name in sorted(n for n in zipped.namelist() if n.endswith(".xml") and "/embeddings/" not in n):
            digest.update(name.encode())
            digest.update(zipped.read(name))
    return digest.hexdigest()


def _slide_size(template: Path | None) -> tuple[Length, Length]:
    if template is None:
        return WIDESCREEN
    source = Presentation(str(template))
    width, height = source.slide_width, source.slide_height
    if not isinstance(width, int) or not isinstance(height, int):
        return WIDESCREEN
    return Emu(width), Emu(height)


def _blank(prs: PresentationDocument) -> SlideLayout:
    layout = prs.slide_layouts.get_by_name("Blank")
    if layout is None:
        raise GuardrailViolation("The presentation has no Blank layout to draw on")
    return layout


def _source_line(fact: Fact) -> str:
    return (
        f"{fact.id} · {fact.label} · {fact.source.template_id} · {', '.join(fact.source.tables)} · "
        f"statement {fact.source.statement_id} · queried {fact.source.as_of:%Y-%m-%d %H:%M} UTC"
    )


def _notes(spec: Slide, facts: FactRegistry) -> str:
    refs = sorted(spec.fact_refs())
    lines = [fill_text(spec.notes, facts)] if spec.notes else []
    lines += [_source_line(facts.get(fact_id)) for fact_id in refs if fact_id in facts]
    for fact_id in refs:
        if fact_id not in facts:
            continue
        source = facts.get(fact_id).source
        if source.sql:
            lines.append(f"{fact_id} SQL:\n{source.sql}")
            lines.append(f"{fact_id} parameters: {json.dumps(source.params, sort_keys=True)}")
        if source.template_sha256:
            lines.append(f"{fact_id} template SHA-256: {source.template_sha256}")
    return "\n".join(lines) or "No data on this slide."
