"""Ports: the interfaces the application depends on. Adapters implement them.

Each port is a small, role-specific Protocol (interface segregation). The application imports only
these and the domain; concrete adapters are chosen in decksmith.bootstrap (dependency inversion).
"""

from decksmith.ports.catalog import Catalog, TableRef
from decksmith.ports.data_source import DataSource, QueryResult
from decksmith.ports.identity import IdentityProvider
from decksmith.ports.llm import LLMGateway, LLMRequest, LLMResponse, Message, Tier
from decksmith.ports.renderer import RenderedDeck, Renderer
from decksmith.ports.state_store import StateStore
from decksmith.ports.templates import SqlTemplate, TemplateParam, TemplateRepository
from decksmith.ports.tracer import Tracer

__all__ = [
    "Catalog",
    "DataSource",
    "IdentityProvider",
    "LLMGateway",
    "LLMRequest",
    "LLMResponse",
    "Message",
    "QueryResult",
    "RenderedDeck",
    "Renderer",
    "SqlTemplate",
    "StateStore",
    "TableRef",
    "TemplateParam",
    "TemplateRepository",
    "Tier",
    "Tracer",
]
