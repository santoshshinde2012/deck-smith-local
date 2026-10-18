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
    band: str
    font_display: str
    font_body: str
    title_treatment: str
    motif: str
    display_bold: bool


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
    band="#E7D3C4",
    font_display="Georgia",
    font_body="Calibri",
    title_treatment="split",
    motif="bars",
    display_bold=False,
)

HARBOR = Theme(
    id="harbor",
    name="Harbor",
    ink="#0C2422",
    muted="#2C4A45",
    paper="#E4F0EC",
    card="#F6FBFA",
    accent="#A83820",
    cover="#062824",
    cover_ink="#E4F0EC",
    cover_muted="#B7CDC6",
    rule="#C5DDD6",
    series=("#062824", "#A83820", "#1F6A62", "#8C5A2B"),
    highlight="#A83820",
    band="#D7E8E2",
    font_display="Calibri",
    font_body="Calibri",
    title_treatment="banner",
    motif="horizon",
    display_bold=False,
)

GRAPHITE = Theme(
    id="graphite",
    name="Graphite",
    ink="#111113",
    muted="#3F3F46",
    paper="#F7F7F8",
    card="#FFFFFF",
    accent="#1D4ED8",
    cover="#111113",
    cover_ink="#F7F7F8",
    cover_muted="#D4D4D8",
    rule="#E4E4E7",
    series=("#111113", "#1D4ED8", "#71717A", "#B45309"),
    highlight="#B45309",
    band="#E4E4E7",
    font_display="Arial",
    font_body="Calibri",
    title_treatment="masthead",
    motif="lattice",
    display_bold=True,
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
