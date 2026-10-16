"""DeckSmith local: governed, data-backed PowerPoint decks, built and tested on a laptop."""

from importlib.metadata import PackageNotFoundError, version

try:  # single source of truth: pyproject.toml (bumped by release-please)
    __version__ = version("deck-smith-local")
except PackageNotFoundError:  # pragma: no cover - running from a source tree without install
    __version__ = "0.0.0"
