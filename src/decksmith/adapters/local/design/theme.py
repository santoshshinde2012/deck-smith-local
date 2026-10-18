"""Design tokens. Colours are hex strings so contrast checks stay free of PowerPoint."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    """One complete, accessible colour and type system."""

    id: str
    name: str
    ink: str
    muted: str
    paper: str
    card: str
    accent: str
    cover: str
    cover_ink: str
    cover_muted: str
    rule: str
    series: tuple[str, ...]
    highlight: str
    font_display: str
    font_body: str


MERIDIAN = Theme(
    id="meridian",
    name="Meridian",
    ink="#1C1915",
    muted="#5C564C",
    paper="#F4F0E8",
    card="#FBF9F5",
    accent="#9C4221",
    cover="#1A3144",
    cover_ink="#F4F0E8",
    cover_muted="#C5D0D6",
    rule="#E3DCD0",
    series=("#1A3144", "#9C4221", "#3E6A74", "#7A5E24"),
    highlight="#9C4221",
    font_display="Georgia",
    font_body="Calibri",
)

HARBOR = Theme(
    id="harbor",
    name="Harbor",
    ink="#10211F",
    muted="#3E534E",
    paper="#F2F6F4",
    card="#FBFEFD",
    accent="#B6402C",
    cover="#0E3330",
    cover_ink="#F2F6F4",
    cover_muted="#C5D5D0",
    rule="#D5E2DC",
    series=("#0E3330", "#B6402C", "#2F6F68", "#9A6230"),
    highlight="#B6402C",
    font_display="Georgia",
    font_body="Calibri",
)

GRAPHITE = Theme(
    id="graphite",
    name="Graphite",
    ink="#18181B",
    muted="#52525B",
    paper="#F4F4F5",
    card="#FFFFFF",
    accent="#1E40AF",
    cover="#18181B",
    cover_ink="#F4F4F5",
    cover_muted="#D4D4D8",
    rule="#E4E4E7",
    series=("#18181B", "#1E40AF", "#52525B", "#9A3412"),
    highlight="#1E40AF",
    font_display="Georgia",
    font_body="Calibri",
)

THEMES: dict[str, Theme] = {theme.id: theme for theme in (MERIDIAN, HARBOR, GRAPHITE)}


def get_theme(theme_id: str) -> Theme:
    """Resolve a theme id. Unknown ids fail at construction, not halfway through a slide."""
    try:
        return THEMES[theme_id]
    except KeyError:
        known = ", ".join(sorted(THEMES))
        raise ValueError(f"unknown theme: {theme_id} (known: {known})") from None


def relative_luminance(hex_color: str) -> float:
    """WCAG relative luminance for an #RRGGBB colour."""

    def channel(value: int) -> float:
        scaled = value / 255
        return scaled / 12.92 if scaled <= 0.04045 else ((scaled + 0.055) / 1.055) ** 2.4

    red, green, blue = _channels(hex_color)
    return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio, from 1 to 21."""
    lighter = max(relative_luminance(foreground), relative_luminance(background))
    darker = min(relative_luminance(foreground), relative_luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def _channels(hex_color: str) -> tuple[int, int, int]:
    text = hex_color.removeprefix("#")
    if len(text) != 6:
        raise ValueError(f"colour must be #RRGGBB: {hex_color}")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
