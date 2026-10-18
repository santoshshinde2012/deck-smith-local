"""Cover treatments. Each theme gets its own title structure and a motif, not a shared placeholder."""

from __future__ import annotations

from typing import Any

from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN

from decksmith.adapters.local.design.canvas import Canvas, add_shape, add_text, folio, paint_background
from decksmith.adapters.local.design.fitting import fit_paragraphs
from decksmith.adapters.local.design.text import fill_text
from decksmith.adapters.local.design.theme import Theme
from decksmith.domain.deckspec import Slide
from decksmith.domain.facts import FactRegistry


def paint_cover(slide: Any, spec: Slide, facts: FactRegistry, theme: Theme, canvas: Canvas, number: int) -> bool:
    """Draw the cover for this theme's title treatment."""
    if theme.title_treatment == "banner":
        return _banner(slide, spec, facts, theme, canvas, number)
    if theme.title_treatment == "masthead":
        return _masthead(slide, spec, facts, theme, canvas, number)
    return _split(slide, spec, facts, theme, canvas, number)


def _split(slide: Any, spec: Slide, facts: FactRegistry, theme: Theme, canvas: Canvas, number: int) -> bool:
    """Meridian: a deep panel for the title, and a small column motif on the paper side."""
    paint_background(slide, theme.cover)
    panel = int(canvas.width * 0.56)
    add_shape(slide, MSO_SHAPE.RECTANGLE, panel, 0, canvas.width - panel, canvas.height, theme.paper)
    add_shape(slide, MSO_SHAPE.RECTANGLE, panel - 45720, 0, 45720, canvas.height, theme.accent)
    _bars(
        slide,
        panel + 640080,
        canvas.height - 1737360,
        1280160,
        3017520,
        (theme.accent, theme.series[0], theme.series[2], theme.highlight, theme.series[0], theme.series[2]),
    )
    title = fill_text(spec.title, facts)
    fit = fit_paragraphs([title], canvas.inches(panel - canvas.margin - 160000), 2.2, max_pt=44, min_pt=26)
    add_text(
        slide,
        "\n".join(fit.lines),
        canvas.margin,
        int(canvas.height * 0.28),
        panel - canvas.margin - 182880,
        2011680,
        font=theme.font_display,
        size=fit.font_pt,
        color=theme.cover_ink,
        bold=theme.display_bold,
    )
    overflow = fit.overflow
    subtitle = fill_text(spec.subtitle, facts)
    if subtitle:
        sub = fit_paragraphs([subtitle], canvas.inches(panel - canvas.margin - 160000), 0.8, max_pt=18, min_pt=14)
        add_text(
            slide,
            "\n".join(sub.lines),
            canvas.margin,
            int(canvas.height * 0.28) + 2103120,
            panel - canvas.margin - 182880,
            731520,
            font=theme.font_body,
            size=sub.font_pt,
            color=theme.cover_muted,
        )
        overflow = overflow or sub.overflow
    add_text(
        slide,
        "DeckSmith",
        canvas.margin,
        canvas.footer_top + 27432,
        1828800,
        274320,
        font=theme.font_body,
        size=12,
        color=theme.cover_muted,
    )
    add_text(
        slide,
        folio(number),
        panel - canvas.margin - 640080,
        canvas.footer_top + 27432,
        548640,
        292608,
        font=theme.font_display,
        size=13,
        color=theme.cover_ink,
        align=PP_ALIGN.RIGHT,
    )
    return overflow


def _banner(slide: Any, spec: Slide, facts: FactRegistry, theme: Theme, canvas: Canvas, number: int) -> bool:
    """Harbor: a full-bleed field, a horizon line, and a run of bars under it."""
    paint_background(slide, theme.cover)
    horizon = int(canvas.height * 0.58)
    add_shape(slide, MSO_SHAPE.RECTANGLE, 0, horizon, canvas.width, 36576, theme.cover_ink)
    bar_top = horizon + 228600
    _bars(
        slide,
        canvas.margin,
        bar_top,
        canvas.footer_top - bar_top - 91440,
        int(canvas.width * 0.42),
        (theme.cover_ink, theme.band, theme.cover_muted, theme.cover_ink, theme.band, theme.cover_muted),
    )
    left_width = int(canvas.width * 0.62)
    title = fill_text(spec.title, facts)
    fit = fit_paragraphs([title], canvas.inches(left_width - canvas.margin), 2.0, max_pt=48, min_pt=28)
    add_text(
        slide,
        "\n".join(fit.lines),
        canvas.margin,
        int(canvas.height * 0.16),
        left_width - canvas.margin,
        1828800,
        font=theme.font_display,
        size=fit.font_pt,
        color=theme.cover_ink,
        bold=theme.display_bold,
    )
    overflow = fit.overflow
    subtitle = fill_text(spec.subtitle, facts)
    if subtitle:
        sub = fit_paragraphs([subtitle], canvas.inches(left_width - canvas.margin), 0.7, max_pt=18, min_pt=14)
        add_text(
            slide,
            "\n".join(sub.lines),
            canvas.margin,
            int(canvas.height * 0.16) + 1920240,
            left_width - canvas.margin,
            548640,
            font=theme.font_body,
            size=sub.font_pt,
            color=theme.cover_muted,
        )
        overflow = overflow or sub.overflow
    add_text(
        slide,
        "DeckSmith",
        canvas.margin,
        canvas.margin,
        1828800,
        274320,
        font=theme.font_body,
        size=12,
        color=theme.cover_muted,
    )
    add_text(
        slide,
        folio(number),
        canvas.width - canvas.margin - 640080,
        canvas.footer_top + 27432,
        548640,
        292608,
        font=theme.font_display,
        size=13,
        color=theme.cover_ink,
        align=PP_ALIGN.RIGHT,
    )
    return overflow


def _masthead(slide: Any, spec: Slide, facts: FactRegistry, theme: Theme, canvas: Canvas, number: int) -> bool:
    """Graphite: a black masthead band, the title on paper, and a lattice in the corner."""
    paint_background(slide, theme.paper)
    band = 1371600
    add_shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, canvas.width, band, theme.cover)
    add_shape(slide, MSO_SHAPE.RECTANGLE, 0, band, canvas.width, 45720, theme.accent)
    add_text(
        slide,
        "DeckSmith",
        canvas.margin,
        320040,
        2743200,
        365760,
        font=theme.font_body,
        size=14,
        color=theme.cover_ink,
        bold=True,
    )
    _lattice(slide, theme, canvas)
    title = fill_text(spec.title, facts)
    fit = fit_paragraphs([title], canvas.inches(canvas.content_width), 1.8, max_pt=48, min_pt=28, bold=True)
    add_text(
        slide,
        "\n".join(fit.lines),
        canvas.margin,
        band + 457200,
        canvas.content_width,
        1645920,
        font=theme.font_display,
        size=fit.font_pt,
        color=theme.ink,
        bold=True,
    )
    overflow = fit.overflow
    subtitle = fill_text(spec.subtitle, facts)
    if subtitle:
        sub = fit_paragraphs([subtitle], canvas.inches(int(canvas.content_width * 0.7)), 0.7, max_pt=18, min_pt=14)
        add_text(
            slide,
            "\n".join(sub.lines),
            canvas.margin,
            band + 457200 + 1737360,
            int(canvas.content_width * 0.7),
            548640,
            font=theme.font_body,
            size=sub.font_pt,
            color=theme.muted,
        )
        overflow = overflow or sub.overflow
    add_text(
        slide,
        folio(number),
        canvas.width - canvas.margin - 640080,
        canvas.footer_top + 27432,
        548640,
        292608,
        font=theme.font_display,
        size=13,
        color=theme.ink,
        align=PP_ALIGN.RIGHT,
        bold=True,
    )
    return overflow


def _bars(slide: Any, left: int, top: int, height: int, width: int, colours: tuple[str, ...]) -> None:
    """A miniature column chart. Heights are a fixed rhythm, not data, so they carry no digits."""
    weights = (0.45, 0.72, 0.38, 0.9, 0.58, 0.8)
    count = len(weights)
    gap = 54864
    bar_w = max(1, (width - gap * (count - 1)) // count)
    for index, weight in enumerate(weights):
        bar_h = max(1, int(height * weight))
        add_shape(
            slide,
            MSO_SHAPE.RECTANGLE,
            left + index * (bar_w + gap),
            top + height - bar_h,
            bar_w,
            bar_h,
            colours[index],
        )


def _lattice(slide: Any, theme: Theme, canvas: Canvas) -> None:
    """A four-by-three modular grid. The accent diagonal is the only strong colour."""
    cell, gap, cols, rows = 137160, 64008, 4, 3
    width = cols * cell + (cols - 1) * gap
    height = rows * cell + (rows - 1) * gap
    left = canvas.width - canvas.margin - width
    top = canvas.footer_top - height - 182880
    for row in range(rows):
        for col in range(cols):
            colour = theme.accent if row == col else theme.band
            add_shape(
                slide,
                MSO_SHAPE.RECTANGLE,
                left + col * (cell + gap),
                top + row * (cell + gap),
                cell,
                cell,
                colour,
            )
