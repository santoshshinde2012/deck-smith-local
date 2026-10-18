"""Build a five-slide contact sheet from the actual sample PPTX (no generated content).

Usage: python scripts/preview_deck.py docs/examples/sample-deck.pptx OUTPUT.png

Requires Pillow and matplotlib. This is a code-rendered preview, not a pixel-exact
PowerPoint/Keynote screenshot: fonts, text inheritance and chart axes are approximated.
Text, shape positions, chart categories and series values come directly from the PPTX.
It supports the text, line and horizontal-bar objects in DeckSmith's default sample.
The PNG metadata records the source PPTX hash and rendering method.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.ticker import MultipleLocator, PercentFormatter
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
from pptx import Presentation
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

EMU_PER_INCH = 914400
SLIDE_WIDTH = 960
GAP = 24


def font_path(bold: bool) -> str:
    name = "Arial Bold.ttf" if bold else "Arial.ttf"
    candidates = [Path("/System/Library/Fonts/Supplemental") / name]
    candidates += [Path("/usr/share/fonts/truetype/dejavu") / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")]
    return str(next((path for path in candidates if path.exists()), candidates[0]))


def wrap(text: str, font: ImageFont.FreeTypeFont, width: float) -> list[str]:
    lines = [""]
    for word in text.split():
        proposal = (lines[-1] + " " + word).strip()
        if lines[-1] and font.getlength(proposal) > width:
            lines.append(word)
        else:
            lines[-1] = proposal
    return lines


def draw_text(image: Image.Image, shape: object, scale: float, points_to_px: float) -> None:
    frame = shape.text_frame
    kind = shape.placeholder_format.type if shape.is_placeholder else None
    title = kind in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE)
    subtitle = kind == PP_PLACEHOLDER.SUBTITLE
    default_size = 44 if title else 32 if subtitle else 18
    x = (shape.left + frame.margin_left) * scale
    y = (shape.top + frame.margin_top) * scale
    width = (shape.width - frame.margin_left - frame.margin_right) * scale
    height = (shape.height - frame.margin_top - frame.margin_bottom) * scale
    paragraphs = []
    for paragraph in frame.paragraphs:
        run = paragraph.runs[0] if paragraph.runs else None
        size = run.font.size if run is not None else paragraph.font.size
        size_pt = size.pt if size is not None else default_size
        font = ImageFont.truetype(font_path(bool(run and run.font.bold)), round(size_pt * points_to_px))
        lines = wrap(paragraph.text, font, width) if frame.word_wrap is not False else [paragraph.text]
        centered = paragraph.alignment == PP_ALIGN.CENTER or (paragraph.alignment is None and (title or subtitle))
        paragraphs.append((lines, font, centered, round(size_pt * points_to_px * 1.2)))
    text_height = sum(len(lines) * step for lines, _, _, step in paragraphs)
    if title or frame.vertical_anchor == MSO_ANCHOR.MIDDLE:
        y += max(0, (height - text_height) / 2)
    draw = ImageDraw.Draw(image)
    for lines, font, centered, step in paragraphs:
        for line in lines:
            left = x + max(0, (width - font.getlength(line)) / 2) if centered else x
            draw.text((left, y), line, font=font, fill="#8a8a8a" if subtitle else "#111111", anchor="lt")
            y += step


def draw_chart(image: Image.Image, shape: object, scale: float) -> None:
    chart = shape.chart
    width, height = round(shape.width * scale), round(shape.height * scale)
    figure, axes = plt.subplots(figsize=(width / 100, height / 100), dpi=100)
    figure.patch.set_facecolor("white")
    categories = [str(category) for category in chart.plots[0].categories]
    for series in chart.series:
        if chart.chart_type == XL_CHART_TYPE.LINE_MARKERS:
            axes.plot(categories, series.values, color="#4F81BD", marker="s", markersize=3, linewidth=1.3)
            axes.yaxis.set_major_formatter(PercentFormatter(1, decimals=1))
            axes.yaxis.set_major_locator(MultipleLocator(0.001))
            axes.grid(axis="y", color="#d6d6d6", linewidth=0.6)
        elif chart.chart_type == XL_CHART_TYPE.BAR_CLUSTERED:
            axes.barh(categories, series.values, color="#4F81BD", height=0.5)
            axes.xaxis.set_major_formatter(PercentFormatter(1, decimals=1))
            axes.xaxis.set_major_locator(MultipleLocator(0.005))
            axes.set_xlim(0, math.ceil(max(series.values) / 0.005) * 0.005)
            axes.grid(axis="x", color="#d6d6d6", linewidth=0.6)
            axes.set_axisbelow(True)
        else:
            raise ValueError(f"Unsupported chart in sample preview: {chart.chart_type}")
    axes.tick_params(labelsize=10, length=0)
    axes.spines[["top", "right"]].set_visible(False)
    for spine in axes.spines.values():
        spine.set_color("#aaaaaa")
        spine.set_linewidth(0.6)
    figure.subplots_adjust(left=0.16, bottom=0.13, right=0.98, top=0.95)
    if chart.has_legend:
        axes.legend([series.name for series in chart.series], fontsize=10)
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=100)
    plt.close(figure)
    buffer.seek(0)
    with Image.open(buffer) as rendered:
        image.paste(rendered.convert("RGB"), (round(shape.left * scale), round(shape.top * scale)))


def render(source: Path, destination: Path) -> None:
    presentation = Presentation(source)
    scale = SLIDE_WIDTH / presentation.slide_width
    slide_height = round(presentation.slide_height * scale)
    rows = math.ceil(len(presentation.slides) / 3)
    contact = Image.new("RGB", (SLIDE_WIDTH * 3 + GAP * 4, slide_height * rows + GAP * (rows + 1)), "#edf0f4")
    for index, slide in enumerate(presentation.slides):
        image = Image.new("RGB", (SLIDE_WIDTH, slide_height), "white")
        for shape in slide.shapes:
            if shape.has_text_frame:
                draw_text(image, shape, scale, scale * EMU_PER_INCH / 72)
            elif shape.has_chart:
                draw_chart(image, shape, scale)
            else:
                raise ValueError(f"Unsupported sample shape: {shape.name}")
        contact.paste(image, (GAP + (index % 3) * (SLIDE_WIDTH + GAP), GAP + (index // 3) * (slide_height + GAP)))
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text(
        "Description", "Code-rendered from actual PPTX shapes, text and series; not a native Office screenshot"
    )
    metadata.add_text("Source-SHA256", hashlib.sha256(source.read_bytes()).hexdigest())
    metadata.add_text("Slide-Count", str(len(presentation.slides)))
    destination.parent.mkdir(parents=True, exist_ok=True)
    contact.save(destination, pnginfo=metadata)
    print(f"{destination}: {contact.width} x {contact.height}; {len(presentation.slides)} slides")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    render(arguments.source, arguments.destination)
