"""Deterministic python-pptx renderer: native, editable charts and text; numbers formatted from facts.

Same spec + same template => same slide XML (checked by content_hash), so golden tests work in CI.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.util import Inches, Length, Pt

from decksmith.domain.deckspec import DeckSpec, Slide
from decksmith.domain.errors import GuardrailViolation
from decksmith.domain.facts import Fact, FactRegistry, format_value
from decksmith.domain.integrity import FACT_PATTERN, chart_consistency, numeric_integrity, source_coverage
from decksmith.ports.renderer import RenderedDeck

# Layouts are picked by NAME from the master, never by index (the design's manifest rule).
LAYOUTS = {
    "title": "Title Slide",
    "section": "Section Header",
    "bullets": "Title and Content",
    "two_content": "Two Content",
    "kpi": "Title Only",
    "chart": "Title Only",
    "appendix_sources": "Title and Content",
}
CHARTS = {
    "line": XL_CHART_TYPE.LINE_MARKERS,
    "bar": XL_CHART_TYPE.BAR_CLUSTERED,
    "column": XL_CHART_TYPE.COLUMN_CLUSTERED,
}
BRAND_MIN_PT = 14
OVERFLOW_CHARS = 520
FIXED_TIMESTAMP = datetime(2026, 1, 1)


class PptxRenderer:
    def __init__(self, output_dir: Path, template_path: Path | None = None) -> None:
        self._out = output_dir
        self._template = template_path

    def render(self, spec: DeckSpec, facts: FactRegistry, run_id: str) -> RenderedDeck:
        issues = numeric_integrity(spec, facts) + chart_consistency(spec, facts) + source_coverage(spec)
        if issues:
            raise GuardrailViolation("Invalid deck: " + "; ".join(f"{i.code}: {i.detail}" for i in issues))
        prs = Presentation(str(self._template)) if self._template else Presentation()
        prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
        layouts = {layout.name: layout for layout in prs.slide_layouts}
        overflow: list[str] = []
        for slide_spec in spec.slides:
            slide = prs.slides.add_slide(layouts[LAYOUTS[slide_spec.layout]])
            if slide.shapes.title is not None:
                slide.shapes.title.text = _fill(slide_spec.title, facts)
            if _draw(slide, slide_spec, facts, prs.slide_width):
                overflow.append(slide_spec.slide_id)
            slide.notes_slide.notes_text_frame.text = _notes(slide_spec, facts)
        props = prs.core_properties
        props.title, props.subject, props.keywords = _fill(spec.title, facts), f"run_id={run_id}", spec.template_id
        props.author, props.revision = "DeckSmith", 1
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
    with zipfile.ZipFile(path) as z:
        for name in sorted(n for n in z.namelist() if n.endswith(".xml") and "/embeddings/" not in n):
            digest.update(name.encode())
            digest.update(z.read(name))
    return digest.hexdigest()


def _fill(text: str, facts: FactRegistry) -> str:
    def value(match: re.Match[str]) -> str:
        fact = facts.get(match.group(1))
        if fact.kind != "scalar" or fact.value is None:
            raise GuardrailViolation(f"Text placeholder needs a scalar fact: {fact.id}")
        return format_value(fact.value, fact.format, fact.unit)

    return FACT_PATTERN.sub(value, text)


def _draw(slide: object, spec: Slide, facts: FactRegistry, width: Length) -> bool:
    shapes = slide.shapes  # type: ignore[attr-defined]
    placeholders = {p.placeholder_format.idx: p for p in slide.placeholders}  # type: ignore[attr-defined]
    if spec.layout in ("title", "section") and 1 in placeholders:
        placeholders[1].text = _fill(spec.subtitle, facts)
    if spec.layout in ("bullets", "two_content") and 1 in placeholders:
        return _bullets(placeholders[1].text_frame, [_fill(b, facts) for b in spec.bullets])
    if spec.layout == "appendix_sources" and 1 in placeholders:
        lines = [_source_line(facts.get(f)) for f in spec.sources if f in facts]
        _bullets(placeholders[1].text_frame, lines or ["No sources"])
        return False  # the sources appendix is dense by design; it is set small, not flagged
    if spec.layout == "kpi":
        _kpis(shapes, spec, facts, width)
        if spec.bullets:
            box = shapes.add_textbox(Inches(0.8), Inches(4.6), width - Inches(1.6), Inches(2))
            return _bullets(box.text_frame, [_fill(b, facts) for b in spec.bullets])
    if spec.layout == "chart" and spec.chart:
        _chart(shapes, spec, facts, width)
    return False


def _bullets(frame: object, lines: list[str], min_pt: int = BRAND_MIN_PT) -> bool:
    frame.clear()  # type: ignore[attr-defined]
    overflow = sum(len(line) for line in lines) > OVERFLOW_CHARS
    size = Pt(min_pt if overflow else 20)
    for i, line in enumerate(lines):
        para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()  # type: ignore[attr-defined]
        para.text = line
        for run in para.runs:
            run.font.size = size
    return overflow


def _kpis(shapes: object, spec: Slide, facts: FactRegistry, width: Length) -> None:
    gap = Inches(0.3)
    box_w = int((width - Inches(1.6) - gap * (len(spec.kpis) - 1)) / len(spec.kpis))
    for i, kpi in enumerate(spec.kpis):
        fact = facts.get(kpi.fact_id)
        box = shapes.add_textbox(Inches(0.8) + i * (box_w + gap), Inches(2.0), box_w, Inches(2.2))  # type: ignore[attr-defined]
        frame = box.text_frame
        if fact.kind != "scalar" or fact.value is None:
            raise GuardrailViolation(f"KPI needs a scalar fact: {fact.id}")
        frame.text = format_value(fact.value, fact.format, fact.unit)
        frame.paragraphs[0].runs[0].font.size = Pt(40)
        frame.paragraphs[0].runs[0].font.bold = True
        label = frame.add_paragraph()
        label.text = _fill(kpi.label, facts)
        label.runs[0].font.size = Pt(16)


def _chart(shapes: object, spec: Slide, facts: FactRegistry, width: Length) -> None:
    assert spec.chart is not None
    first = facts.get(spec.chart.series[0].fact_id)
    data = CategoryChartData(  # type: ignore[no-untyped-call]
        number_format="0.0%" if first.format == "pct1" else "#,##0"
    )
    data.categories = list(first.categories)
    for series in spec.chart.series:
        data.add_series(_fill(series.name, facts), list(facts.get(series.fact_id).values))  # type: ignore[no-untyped-call]
    frame = shapes.add_chart(  # type: ignore[attr-defined]
        CHARTS[spec.chart.type],
        Inches(0.8),
        Inches(1.6),  # type: ignore[attr-defined]
        width - Inches(1.6),
        Inches(5.2),
        data,
    )
    chart = frame.chart
    chart.has_legend = len(spec.chart.series) > 1
    if chart.has_legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False


def _source_line(fact: Fact) -> str:
    return (
        f"{fact.id} · {fact.label} · {fact.source.template_id} · {', '.join(fact.source.tables)} · "
        f"statement {fact.source.statement_id} · queried {fact.source.as_of:%Y-%m-%d %H:%M} UTC"
    )


def _notes(spec: Slide, facts: FactRegistry) -> str:
    refs = sorted(spec.fact_refs())
    lines = [_fill(spec.notes, facts)] if spec.notes else []
    lines += [_source_line(facts.get(f)) for f in refs if f in facts]
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
