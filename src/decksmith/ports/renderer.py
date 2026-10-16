"""Renderer port: turns a validated DeckSpec plus facts into a file."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from decksmith.domain.deckspec import DeckSpec
from decksmith.domain.facts import FactRegistry


class RenderedDeck(BaseModel):
    model_config = ConfigDict(frozen=True)
    path: str
    sha256: str
    content_hash: str  # hash of the slide XML only: stable across runs for the same spec and template
    slide_count: int
    overflow_slides: tuple[str, ...] = ()


@runtime_checkable
class Renderer(Protocol):
    def render(self, spec: DeckSpec, facts: FactRegistry, run_id: str) -> RenderedDeck: ...
