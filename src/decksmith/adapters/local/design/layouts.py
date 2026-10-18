"""One painter per slide layout. A new layout is a new painter registered here, not a branch in the renderer."""

from __future__ import annotations

from typing import Any, Protocol

from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

from decksmith.adapters.local.design.canvas import (
    Canvas,
    add_shape,
    add_text,
    card_spans,
    folio,
    footer_sources,
    paint_action_title,
    paint_background,
    paint_footer,
)
from decksmith.adapters.local.design.charts import add_chart
from decksmith.adapters.local.design.fitting import fit_paragraphs, single_line, too_dense
from decksmith.adapters.local.design.text import fill_text
from decksmith.adapters.local.design.theme import Theme
from decksmith.domain.deckspec import Slide
from decksmith.domain.errors import GuardrailViolation
from decksmith.domain.facts import Fact, FactRegistry, format_value


class SlidePainter(Protocol):
    """Renders one layout. Returns whether body text still overflowed at the minimum size."""

    layout: str

    def paint(
        self, slide: Any, spec: Slide, facts: FactRegistry, theme: Theme, canvas: Canvas, number: int
    ) -> bool: ...


class LayoutRegistry:
    """Open/closed collection of painters, keyed by the DeckSpec layout name."""

    def __init__(self, painters: tuple[SlidePainter, ...] | list[SlidePainter]) -> None:
        self._painters: dict[str, SlidePainter] = {}
        for painter in painters:
            self._painters[painter.layout] = painter

    def layouts(self) -> tuple[str, ...]:
        return tuple(sorted(self._painters))

    def paint(self, slide: Any, spec: Slide, facts: FactRegistry, theme: Theme, canvas: Canvas, number: int) -> bool:
        return self._painters[spec.layout].paint(slide, spec, facts, theme, canvas, number)


class TitleLayout:
    layout = "title"

    def paint(self, slide: Any, spec: Slide, facts: FactRegistry, theme: Theme, canvas: Canvas, number: int) -> bool:
        paint_background(slide, theme.cover)
        panel = int(canvas.width * 0.58)
        add_shape(slide, MSO_SHAPE.RECTANGLE, panel, 0, canvas.width - panel, canvas.height, theme.paper)
        add_shape(slide, MSO_SHAPE.RECTANGLE, panel - 54864, 0, 54864, canvas.height, theme.accent)
        _mark(slide, theme, canvas, inverse=True)
        title = fill_text(spec.title, facts)
        fit = fit_paragraphs([title], canvas.inches(panel - canvas.margin - 109728), 2.2, max_pt=44, min_pt=26)
        add_text(
            slide,
            "\n".join(fit.lines),
            canvas.margin,
            int(canvas.height * 0.30),
            panel - canvas.margin - 137160,
            2011680,
            font=theme.font_display,
            size=fit.font_pt,
            color=theme.cover_ink,
        )
        subtitle = fill_text(spec.subtitle, facts)
        overflow = fit.overflow
        if subtitle:
            sub = fit_paragraphs([subtitle], canvas.inches(panel - canvas.margin - 109728), 0.8, max_pt=18, min_pt=14)
            add_text(
                slide,
                "\n".join(sub.lines),
                canvas.margin,
                int(canvas.height * 0.30) + 2103120,
                panel - canvas.margin - 137160,
                731520,
                font=theme.font_body,
                size=sub.font_pt,
                color=theme.cover_muted,
            )
            overflow = overflow or sub.overflow
        _quiet_mark(slide, theme, canvas, panel)
        add_text(
            slide,
            folio(number),
            panel - canvas.margin - 640080,
            canvas.footer_top + 45720,
            640080,
            292608,
            font=theme.font_display,
            size=13,
            color=theme.cover_ink,
            align=PP_ALIGN.RIGHT,
        )
        return overflow


class SectionLayout:
    layout = "section"

    def paint(self, slide: Any, spec: Slide, facts: FactRegistry, theme: Theme, canvas: Canvas, number: int) -> bool:
        paint_background(slide, theme.cover)
        left, width = canvas.span(0, 9)
        add_shape(slide, MSO_SHAPE.RECTANGLE, left, int(canvas.height * 0.36), 365760, 27432, theme.accent)
        title = fill_text(spec.title, facts)
        fit = fit_paragraphs([title], canvas.inches(width), 1.6, max_pt=40, min_pt=24)
        add_text(
            slide,
            "\n".join(fit.lines),
            left,
            int(canvas.height * 0.40),
            width,
            1463040,
            font=theme.font_display,
            size=fit.font_pt,
            color=theme.cover_ink,
        )
        overflow = fit.overflow
        subtitle = fill_text(spec.subtitle, facts)
        if subtitle:
            sub = fit_paragraphs([subtitle], canvas.inches(width), 0.6, max_pt=18, min_pt=14)
            add_text(
                slide,
                "\n".join(sub.lines),
                left,
                int(canvas.height * 0.40) + 1554480,
                width,
                548640,
                font=theme.font_body,
                size=sub.font_pt,
                color=theme.cover_muted,
            )
            overflow = overflow or sub.overflow
        paint_footer(slide, canvas, theme, number, "", inverse=True)
        return overflow


class AgendaLayout:
    layout = "agenda"

    def paint(self, slide: Any, spec: Slide, facts: FactRegistry, theme: Theme, canvas: Canvas, number: int) -> bool:
        paint_background(slide, theme.paper)
        overflow = paint_action_title(slide, fill_text(spec.title, facts), theme, canvas)
        lines = [fill_text(bullet, facts) for bullet in spec.bullets]
        overflow = overflow or _rows(slide, lines, theme, canvas, numbered=True) or too_dense(lines)
        paint_footer(slide, canvas, theme, number, _sources(spec, facts))
        return overflow


class KpiLayout:
    layout = "kpi"

    def paint(self, slide: Any, spec: Slide, facts: FactRegistry, theme: Theme, canvas: Canvas, number: int) -> bool:
        paint_background(slide, theme.paper)
        overflow = paint_action_title(slide, fill_text(spec.title, facts), theme, canvas)
        spans = card_spans(len(spec.kpis))
        top = 1463040  # 1.60 in
        height = 2057400  # 2.25 in
        for (start, count), kpi in zip(spans, spec.kpis, strict=True):
            left, width = canvas.span(start, count)
            fact = facts.get(kpi.fact_id)
            if fact.kind != "scalar" or fact.value is None:
                raise GuardrailViolation(f"KPI needs a scalar fact: {fact.id}")
            add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height, theme.card, radius=0.08)
            add_shape(slide, MSO_SHAPE.RECTANGLE, left, top, width, 36576, theme.accent)
            value = fill_text(format_kpi(fact), facts)
            value_fit = fit_paragraphs(
                [value], canvas.inches(width - 182880), 0.8, max_pt=40, min_pt=22, bold=True, leading=1.0
            )
            add_text(
                slide,
                value,
                left + 137160,
                top + 228600,
                width - 228600,
                822960,
                font=theme.font_display,
                size=value_fit.font_pt,
                color=theme.ink,
                bold=True,
                anchor=MSO_ANCHOR.MIDDLE,
            )
            label = fill_text(kpi.label, facts)
            label_fit = fit_paragraphs([label], canvas.inches(width - 228600), 0.7, max_pt=14, min_pt=11)
            add_text(
                slide,
                "\n".join(label_fit.lines),
                left + 137160,
                top + 1097280,
                width - 228600,
                640080,
                font=theme.font_body,
                size=label_fit.font_pt,
                color=theme.muted,
            )
            overflow = overflow or value_fit.overflow or label_fit.overflow
        lines = [fill_text(bullet, facts) for bullet in spec.bullets]
        if lines:
            callout_top = 3794760  # 4.15 in, just under the cards
            callout_height = min(1188720, canvas.footer_top - callout_top - 91440)
            if callout_height > 274320:
                overflow = overflow or _callout(slide, lines, theme, canvas, callout_top, callout_height)
            overflow = overflow or too_dense(lines)
        paint_footer(slide, canvas, theme, number, _sources(spec, facts))
        return overflow


class ChartLayout:
    layout = "chart"

    def paint(self, slide: Any, spec: Slide, facts: FactRegistry, theme: Theme, canvas: Canvas, number: int) -> bool:
        paint_background(slide, theme.paper)
        overflow = paint_action_title(slide, fill_text(spec.title, facts), theme, canvas)
        assert spec.chart is not None
        left, width = canvas.span(0, 12)
        top = 1554480
        height = canvas.footer_top - top - 91440
        add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height, theme.card, radius=0.04)
        categories, series, fmt = _series(spec, facts)
        pad = 137160
        add_chart(
            slide,
            spec.chart.type,
            categories,
            series,
            left + pad,
            top + pad,
            width - 2 * pad,
            height - 2 * pad,
            theme,
            fmt,
        )
        paint_footer(slide, canvas, theme, number, _sources(spec, facts))
        return overflow


class BulletsLayout:
    layout = "bullets"

    def paint(self, slide: Any, spec: Slide, facts: FactRegistry, theme: Theme, canvas: Canvas, number: int) -> bool:
        return _text_slide(slide, spec, facts, theme, canvas, number, columns=1)


class TwoContentLayout:
    layout = "two_content"

    def paint(self, slide: Any, spec: Slide, facts: FactRegistry, theme: Theme, canvas: Canvas, number: int) -> bool:
        return _text_slide(slide, spec, facts, theme, canvas, number, columns=2)


class ComparisonLayout:
    layout = "comparison"

    def paint(self, slide: Any, spec: Slide, facts: FactRegistry, theme: Theme, canvas: Canvas, number: int) -> bool:
        paint_background(slide, theme.paper)
        overflow = paint_action_title(slide, fill_text(spec.title, facts), theme, canvas)
        top = 1554480
        height = canvas.footer_top - top - 91440
        for index, column in enumerate(spec.columns):
            left, width = canvas.span(0 if index == 0 else 6, 6)
            add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height, theme.card, radius=0.06)
            heading = fill_text(column.heading, facts)
            add_text(
                slide,
                heading,
                left + 182880,
                top + 182880,
                width - 320040,
                365760,
                font=theme.font_display,
                size=20,
                color=theme.accent,
            )
            lines = [fill_text(bullet, facts) for bullet in column.bullets]
            body = fit_paragraphs(
                [f"–  {line}" for line in lines],
                canvas.inches(width - 365760),
                canvas.inches(height - 731520),
                max_pt=16,
                min_pt=12,
            )
            add_text(
                slide,
                "\n".join(body.lines),
                left + 182880,
                top + 640080,
                width - 320040,
                height - 822960,
                font=theme.font_body,
                size=body.font_pt,
                color=theme.ink,
            )
            overflow = overflow or body.overflow or too_dense(lines)
        paint_footer(slide, canvas, theme, number, _sources(spec, facts))
        return overflow


class TimelineLayout:
    layout = "timeline"

    def paint(self, slide: Any, spec: Slide, facts: FactRegistry, theme: Theme, canvas: Canvas, number: int) -> bool:
        paint_background(slide, theme.paper)
        overflow = paint_action_title(slide, fill_text(spec.title, facts), theme, canvas)
        count = len(spec.milestones)
        left, total = canvas.span(0, 12)
        axis = 3657600  # 4.0 in
        add_shape(slide, MSO_SHAPE.RECTANGLE, left, axis, total, 13716, theme.rule)
        slot = total // count
        for index, milestone in enumerate(spec.milestones):
            center = left + slot * index + slot // 2
            add_shape(
                slide,
                MSO_SHAPE.OVAL,
                center - 64008,
                axis - 54864,
                128016,
                128016,
                theme.accent if index == count - 1 else theme.ink,
            )
            label = fill_text(milestone.label, facts)
            detail = fill_text(milestone.detail, facts)
            label_fit = fit_paragraphs([label], canvas.inches(slot - 91440), 0.7, max_pt=16, min_pt=12)
            detail_fit = fit_paragraphs([detail], canvas.inches(slot - 91440), 1.1, max_pt=13, min_pt=11)
            add_text(
                slide,
                "\n".join(label_fit.lines),
                left + slot * index + 45720,
                axis - 822960,
                slot - 91440,
                640080,
                font=theme.font_display,
                size=label_fit.font_pt,
                color=theme.ink,
                align=PP_ALIGN.CENTER,
            )
            add_text(
                slide,
                "\n".join(detail_fit.lines),
                left + slot * index + 45720,
                axis + 182880,
                slot - 91440,
                1005840,
                font=theme.font_body,
                size=detail_fit.font_pt,
                color=theme.muted,
                align=PP_ALIGN.CENTER,
            )
            overflow = overflow or label_fit.overflow or detail_fit.overflow
        paint_footer(slide, canvas, theme, number, _sources(spec, facts))
        return overflow


class QuoteLayout:
    layout = "quote"

    def paint(self, slide: Any, spec: Slide, facts: FactRegistry, theme: Theme, canvas: Canvas, number: int) -> bool:
        paint_background(slide, theme.paper)
        overflow = paint_action_title(slide, fill_text(spec.title, facts), theme, canvas)
        left, width = canvas.span(1, 10)
        add_shape(slide, MSO_SHAPE.RECTANGLE, left, 1828800, 54864, 2743200, theme.accent)
        quote = fill_text(spec.quote, facts)
        fit = fit_paragraphs([quote], canvas.inches(width - 274320), 2.4, max_pt=32, min_pt=18)
        add_text(
            slide,
            "\n".join(fit.lines),
            left + 228600,
            1828800,
            width - 274320,
            2194560,
            font=theme.font_display,
            size=fit.font_pt,
            color=theme.ink,
            anchor=MSO_ANCHOR.MIDDLE,
        )
        overflow = overflow or fit.overflow
        attribution = fill_text(spec.attribution, facts)
        if attribution:
            add_text(
                slide,
                attribution,
                left + 228600,
                4114800,
                width - 274320,
                365760,
                font=theme.font_body,
                size=14,
                color=theme.muted,
            )
        paint_footer(slide, canvas, theme, number, _sources(spec, facts))
        return overflow


class SourcesLayout:
    layout = "appendix_sources"

    def paint(self, slide: Any, spec: Slide, facts: FactRegistry, theme: Theme, canvas: Canvas, number: int) -> bool:
        paint_background(slide, theme.paper)
        paint_action_title(slide, fill_text(spec.title, facts), theme, canvas)
        rows = [facts.get(fact_id) for fact_id in spec.sources if fact_id in facts]
        left, width = canvas.span(0, 12)
        top = 1600200
        available = canvas.footer_top - top - 91440
        if not rows:
            add_text(slide, "No sources", left, top, width, 365760, font=theme.font_body, size=16, color=theme.muted)
        else:
            row_h = min(731520, available // len(rows))
            size = 15 if row_h >= 640080 else 12
            label_width = int(width * 0.36)
            meta_left = left + 1005840 + label_width
            meta_width = max(1, width - (meta_left - left))
            for index, fact in enumerate(rows):
                y = top + index * row_h
                add_shape(slide, MSO_SHAPE.RECTANGLE, left, y + row_h - 9144, width, 9144, theme.rule)
                add_text(
                    slide,
                    f"{fact.id} ·",
                    left,
                    y,
                    914400,
                    row_h - 27432,
                    font=theme.font_display,
                    size=size,
                    color=theme.accent,
                    anchor=MSO_ANCHOR.MIDDLE,
                )
                add_text(
                    slide,
                    single_line(fact.label, canvas.inches(label_width), size),
                    left + 1005840,
                    y,
                    label_width,
                    row_h - 27432,
                    font=theme.font_body,
                    size=size,
                    color=theme.ink,
                    anchor=MSO_ANCHOR.MIDDLE,
                )
                meta = f"{fact.source.template_id}    {', '.join(fact.source.tables)}"
                add_text(
                    slide,
                    single_line(meta, canvas.inches(meta_width), max(11, size - 2)),
                    meta_left,
                    y,
                    meta_width,
                    row_h - 27432,
                    font=theme.font_body,
                    size=max(11, size - 2),
                    color=theme.muted,
                    anchor=MSO_ANCHOR.MIDDLE,
                )
        paint_footer(slide, canvas, theme, number, "")
        return False


def default_registry() -> LayoutRegistry:
    return LayoutRegistry(
        (
            TitleLayout(),
            SectionLayout(),
            AgendaLayout(),
            KpiLayout(),
            ChartLayout(),
            BulletsLayout(),
            TwoContentLayout(),
            ComparisonLayout(),
            TimelineLayout(),
            QuoteLayout(),
            SourcesLayout(),
        )
    )


def format_kpi(fact: Fact) -> str:
    if fact.value is None:
        raise GuardrailViolation(f"KPI needs a scalar fact: {fact.id}")
    return format_value(fact.value, fact.format, fact.unit)


def _series(spec: Slide, facts: FactRegistry) -> tuple[tuple[str, ...], tuple[tuple[str, tuple[float, ...]], ...], str]:
    assert spec.chart is not None
    plotted: list[tuple[str, tuple[float, ...]]] = []
    categories: tuple[str, ...] = ()
    fmt = "decimal2"
    for series in spec.chart.series:
        fact = facts.get(series.fact_id)
        if fact.kind != "series":
            raise GuardrailViolation(f"Chart needs a series fact: {fact.id}")
        categories = fact.categories
        fmt = fact.format
        plotted.append((fill_text(series.name, facts), fact.values))
    return categories, tuple(plotted), fmt


def _sources(spec: Slide, facts: FactRegistry) -> str:
    labels: list[str] = []
    for fact_id in spec.sources:
        if fact_id in facts:
            label = facts.get(fact_id).label
            if label not in labels:
                labels.append(label)
    return footer_sources(labels)


def _text_slide(
    slide: Any, spec: Slide, facts: FactRegistry, theme: Theme, canvas: Canvas, number: int, *, columns: int
) -> bool:
    paint_background(slide, theme.paper)
    overflow = paint_action_title(slide, fill_text(spec.title, facts), theme, canvas)
    lines = [fill_text(bullet, facts) for bullet in spec.bullets]
    if columns == 1:
        overflow = overflow or _rows(slide, lines, theme, canvas, numbered=False)
    else:
        midpoint = (len(lines) + 1) // 2
        overflow = overflow or _column_block(slide, lines[:midpoint], theme, canvas, 0, 6)
        overflow = overflow or _column_block(slide, lines[midpoint:], theme, canvas, 6, 6)
        rule_left, _ = canvas.span(6, 6)
        add_shape(
            slide,
            MSO_SHAPE.RECTANGLE,
            rule_left - canvas.gutter // 2,
            1645920,
            9144,
            canvas.footer_top - 1828800,
            theme.rule,
        )
    overflow = overflow or too_dense(lines)
    paint_footer(slide, canvas, theme, number, _sources(spec, facts))
    return overflow


def _rows(slide: Any, lines: list[str], theme: Theme, canvas: Canvas, *, numbered: bool) -> bool:
    if not lines:
        return False
    left, width = canvas.span(0, 12)
    top = 1645920
    available = canvas.footer_top - top - 91440
    row_h = min(640080, available // len(lines))
    overflow = False
    for index, line in enumerate(lines):
        y = top + index * row_h
        wrapped = fit_paragraphs(
            [line], canvas.inches(width - 822960), canvas.inches(max(row_h - 45720, 1)), max_pt=18, min_pt=12
        )
        if numbered:
            add_text(
                slide,
                folio(index + 1),
                left,
                y,
                640080,
                row_h,
                font=theme.font_display,
                size=wrapped.font_pt,
                color=theme.accent,
                anchor=MSO_ANCHOR.MIDDLE,
            )
        else:
            add_shape(
                slide,
                MSO_SHAPE.OVAL,
                left,
                y + row_h // 2 - 27432,
                54864,
                54864,
                theme.accent,
            )
        add_text(
            slide,
            "\n".join(wrapped.lines),
            left + 822960,
            y,
            width - 822960,
            row_h,
            font=theme.font_body,
            size=wrapped.font_pt,
            color=theme.ink,
            anchor=MSO_ANCHOR.MIDDLE,
        )
        overflow = overflow or wrapped.overflow
    return overflow


def _column_block(slide: Any, lines: list[str], theme: Theme, canvas: Canvas, start: int, count: int) -> bool:
    if not lines:
        return False
    left, width = canvas.span(start, count)
    fit = fit_paragraphs([f"–  {line}" for line in lines], canvas.inches(width - 182880), 4.6, max_pt=18, min_pt=12)
    add_text(
        slide,
        "\n".join(fit.lines),
        left,
        1737360,
        width - 182880,
        canvas.footer_top - 1920240,
        font=theme.font_body,
        size=fit.font_pt,
        color=theme.ink,
    )
    return fit.overflow


def _callout(slide: Any, lines: list[str], theme: Theme, canvas: Canvas, top: int, height: int) -> bool:
    left, width = canvas.span(0, 12)
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height, theme.card, radius=0.08)
    add_shape(slide, MSO_SHAPE.RECTANGLE, left, top, 54864, height, theme.accent)
    fit = fit_paragraphs(lines, canvas.inches(width - 457200), canvas.inches(height - 182880), max_pt=16, min_pt=12)
    add_text(
        slide,
        "\n".join(fit.lines),
        left + 274320,
        top + 91440,
        width - 411480,
        height - 182880,
        font=theme.font_body,
        size=fit.font_pt,
        color=theme.ink,
        anchor=MSO_ANCHOR.MIDDLE,
    )
    return fit.overflow


def _mark(slide: Any, theme: Theme, canvas: Canvas, *, inverse: bool) -> None:
    add_text(
        slide,
        "DeckSmith",
        canvas.margin,
        canvas.height - 822960,
        1828800,
        274320,
        font=theme.font_body,
        size=12,
        color=theme.cover_muted if inverse else theme.muted,
    )


def _quiet_mark(slide: Any, theme: Theme, canvas: Canvas, panel: int) -> None:
    size = 1645920
    left = panel + (canvas.width - panel - size) // 2
    top = (canvas.height - size) // 2
    add_shape(slide, MSO_SHAPE.OVAL, left, top, size, size, None, line=theme.accent, line_pt=1.25)
