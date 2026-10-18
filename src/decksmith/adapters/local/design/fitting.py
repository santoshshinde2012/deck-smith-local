"""Estimate how text sits in a box, and shrink it before it spills.

PowerPoint's auto-fit is not stable across hosts, so the renderer chooses a size up front.
The estimate is deliberately a little wide, so a host that wraps slightly differently still fits.
"""

from __future__ import annotations

from dataclasses import dataclass

# An executive bullet block longer than this is too dense even if the type could shrink to fit.
DENSITY_LIMIT = 520


@dataclass(frozen=True)
class Fit:
    """A font size and the wrapped lines that size produces."""

    font_pt: int
    lines: tuple[str, ...]
    overflow: bool


def too_dense(paragraphs: list[str], limit: int = DENSITY_LIMIT) -> bool:
    """True when body copy exceeds the density budget for one slide."""
    return sum(len(paragraph) for paragraph in paragraphs) > limit


def wrap(text: str, width_in: float, font_pt: int, *, bold: bool = False) -> tuple[str, ...]:
    """Greedy word wrap. Over-long words are broken so a single token cannot escape the box."""
    if width_in <= 0 or font_pt <= 0:
        return (text,) if text else ()
    max_chars = max(1, int((width_in * 72) / (font_pt * (0.56 if bold else 0.50))))
    words = text.split()
    if not words:
        return ()
    lines: list[str] = []
    current = ""
    for word in words:
        pieces = _chunks(word, max_chars)
        for piece in pieces:
            proposal = piece if not current else f"{current} {piece}"
            if len(proposal) <= max_chars:
                current = proposal
            else:
                if current:
                    lines.append(current)
                current = piece
    if current:
        lines.append(current)
    return tuple(lines)


def fit_paragraphs(
    paragraphs: list[str],
    width_in: float,
    height_in: float,
    *,
    max_pt: int,
    min_pt: int,
    bold: bool = False,
    leading: float = 1.28,
) -> Fit:
    """Largest size in ``[min_pt, max_pt]`` whose wrapped block fits. Overflows only below ``min_pt``."""
    blocks = [paragraph for paragraph in paragraphs if paragraph]
    if not blocks:
        return Fit(max_pt, (), False)
    for size in range(max_pt, min_pt - 1, -1):
        lines = _lines(blocks, width_in, size, bold)
        if size * leading * len(lines) <= height_in * 72 + 0.01:
            return Fit(size, lines, False)
    lines = _lines(blocks, width_in, min_pt, bold)
    overflow = min_pt * leading * len(lines) > height_in * 72 + 0.01
    return Fit(min_pt, lines, overflow)


def single_line(text: str, width_in: float, font_pt: int) -> str:
    """One line, with an ellipsis when the source is wider than the box."""
    if not text:
        return ""
    if len(wrap(text, width_in, font_pt)) <= 1:
        return text
    kept: list[str] = []
    for word in text.split():
        trial = " ".join([*kept, word]) + "…"
        if len(wrap(trial, width_in, font_pt)) > 1:
            break
        kept.append(word)
    return (" ".join(kept) + "…") if kept else "…"


def _lines(paragraphs: list[str], width_in: float, font_pt: int, bold: bool) -> tuple[str, ...]:
    lines: list[str] = []
    for paragraph in paragraphs:
        lines.extend(wrap(paragraph, width_in, font_pt, bold=bold))
    return tuple(lines)


def _chunks(word: str, size: int) -> tuple[str, ...]:
    if len(word) <= size:
        return (word,)
    return tuple(word[index : index + size] for index in range(0, len(word), size))
