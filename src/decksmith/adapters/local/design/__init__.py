"""Visual system for native PowerPoint decks: themes, fitting, and slide painters."""

from decksmith.adapters.local.design.layouts import LayoutRegistry, default_registry
from decksmith.adapters.local.design.theme import Theme, get_theme

__all__ = ["LayoutRegistry", "Theme", "default_registry", "get_theme"]
