"""Native, editable charts with the chartjunk removed and one point called out.

Direct labels replace the value axis when a single series has few points. A longer series, or
more than one series, keeps a quiet axis and a legend. The highlighted point is the latest
period on a line and the extreme value on a bar or column.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import (
    XL_CHART_TYPE,
    XL_LABEL_POSITION,
    XL_LEGEND_POSITION,
    XL_MARKER_STYLE,
    XL_TICK_MARK,
)
from pptx.util import Emu, Pt

from decksmith.adapters.local.design.canvas import rgb
from decksmith.adapters.local.design.theme import Theme
from decksmith.domain.facts import FactFormat

CHARTS = {
    "line": XL_CHART_TYPE.LINE_MARKERS,
    "bar": XL_CHART_TYPE.BAR_CLUSTERED,
    "column": XL_CHART_TYPE.COLUMN_CLUSTERED,
}

_NUMBER_FORMATS: dict[str, str] = {
    "pct1": "0.0%",
    "int": "#,##0",
    "currency0": "#,##0",
    "decimal2": "0.00",
}


def highlight_index(chart_type: str, values: Sequence[float]) -> int:
    """The point a reader should see first. Ties keep the earliest category."""
    if not values:
        return 0
    if chart_type == "line":
        return len(values) - 1
    return max(range(len(values)), key=lambda index: (values[index], -index))


def direct_labels(category_count: int, series_count: int) -> bool:
    """Label every point only when the labels will not collide."""
    return series_count == 1 and 0 < category_count <= 6


def number_format(fmt: FactFormat | str) -> str:
    return _NUMBER_FORMATS.get(fmt, "General")


def add_chart(
    slide: Any,
    chart_type: str,
    categories: Sequence[str],
    series: Sequence[tuple[str, Sequence[float]]],
    left: int,
    top: int,
    width: int,
    height: int,
    theme: Theme,
    fmt: str,
) -> None:
    """Draw one native chart and style it from the theme. The workbook stays editable."""
    data = CategoryChartData(number_format=number_format(fmt))  # type: ignore[no-untyped-call]
    data.categories = list(categories)
    for name, values in series:
        data.add_series(name, list(values))  # type: ignore[no-untyped-call]
    frame = slide.shapes.add_chart(CHARTS[chart_type], Emu(left), Emu(top), Emu(width), Emu(height), data)
    chart = frame.chart
    chart.has_title = False
    label_points = direct_labels(len(categories), len(series))
    _headroom(chart, chart_type, series, label_points=label_points)
    _axes(chart, theme, fmt, label_points=label_points)
    if label_points:
        _data_labels(chart, theme, fmt, chart_type)
    _paint_all(chart, chart_type, series, theme, label_points=label_points)
    if len(series) > 1:
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = True
        chart.legend.font.size = Pt(12)
        chart.legend.font.name = theme.font_body
        chart.legend.font.color.rgb = rgb(theme.muted)
    else:
        chart.has_legend = False


def _headroom(
    chart: Any,
    chart_type: str,
    series: Sequence[tuple[str, Sequence[float]]],
    *,
    label_points: bool,
) -> None:
    """Leave room for a direct label without flattening a line onto a zero baseline."""
    if not label_points or not series:
        return
    values = [value for _, points in series for value in points]
    if not values:
        return
    floor, peak = min(values), max(values)
    if chart_type in ("bar", "column"):
        chart.value_axis.minimum_scale = min(0.0, floor)
        chart.value_axis.maximum_scale = peak * 1.28 if peak > 0 else 1
        return
    span = peak - floor
    if span <= 0:
        return
    chart.value_axis.minimum_scale = floor - span * 0.45
    chart.value_axis.maximum_scale = peak + span * 0.55


def _axes(chart: Any, theme: Theme, fmt: str, *, label_points: bool) -> None:
    category = chart.category_axis
    category.has_major_gridlines = False
    category.major_tick_mark = XL_TICK_MARK.NONE
    category.minor_tick_mark = XL_TICK_MARK.NONE
    category.format.line.color.rgb = rgb(theme.rule)
    category.tick_labels.font.size = Pt(12)
    category.tick_labels.font.name = theme.font_body
    category.tick_labels.font.color.rgb = rgb(theme.ink)
    value = chart.value_axis
    value.major_tick_mark = XL_TICK_MARK.NONE
    value.minor_tick_mark = XL_TICK_MARK.NONE
    value.format.line.fill.background()
    if label_points:
        value.visible = False
        value.has_major_gridlines = False
        return
    value.visible = True
    value.has_major_gridlines = True
    value.major_gridlines.format.line.color.rgb = rgb(theme.rule)
    value.major_gridlines.format.line.width = Pt(0.75)
    value.tick_labels.font.size = Pt(11)
    value.tick_labels.font.name = theme.font_body
    value.tick_labels.font.color.rgb = rgb(theme.muted)
    value.tick_labels.number_format = number_format(fmt)


def _data_labels(chart: Any, theme: Theme, fmt: str, chart_type: str) -> None:
    plot = chart.plots[0]
    plot.has_data_labels = True
    labels = plot.data_labels
    labels.show_value = True
    labels.show_category_name = False
    labels.show_series_name = False
    labels.show_percentage = False
    labels.number_format = number_format(fmt)
    labels.font.size = Pt(11)
    labels.font.name = theme.font_body
    labels.font.color.rgb = rgb(theme.ink)
    labels.position = XL_LABEL_POSITION.RIGHT if chart_type == "bar" else XL_LABEL_POSITION.ABOVE


def _paint_all(
    chart: Any,
    chart_type: str,
    series: Sequence[tuple[str, Sequence[float]]],
    theme: Theme,
    *,
    label_points: bool,
) -> None:
    if chart_type in ("bar", "column"):
        chart.plots[0].gap_width = 80
        chart.plots[0].vary_by_categories = False
    for index, plotted in enumerate(chart.series):
        base = theme.series[index % len(theme.series)]
        focus = highlight_index(chart_type, series[index][1])
        if chart_type == "line":
            plotted.format.line.color.rgb = rgb(base)
            plotted.format.line.width = Pt(2.25)
            plotted.marker.style = XL_MARKER_STYLE.CIRCLE
            plotted.marker.size = 8
            plotted.marker.format.fill.solid()
            plotted.marker.format.fill.fore_color.rgb = rgb(base)
            plotted.marker.format.line.fill.background()
            plotted.smooth = False
        else:
            plotted.format.fill.solid()
            plotted.format.fill.fore_color.rgb = rgb(base)
            plotted.format.line.fill.background()
        for point_index, point in enumerate(plotted.points):
            color = theme.highlight if point_index == focus else base
            if chart_type == "line":
                point.marker.format.fill.solid()
                point.marker.format.fill.fore_color.rgb = rgb(color)
                point.marker.format.line.fill.background()
            else:
                point.format.fill.solid()
                point.format.fill.fore_color.rgb = rgb(color)
                point.format.line.fill.background()
            if label_points:
                label = point.data_label
                label.font.size = Pt(12 if point_index == focus else 11)
                label.font.bold = point_index == focus
                label.font.name = theme.font_body
                label.font.color.rgb = rgb(theme.highlight if point_index == focus else theme.ink)
