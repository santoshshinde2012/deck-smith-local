"""Composition root. The ONLY module that imports concrete adapters.

Each port has a small registry of factories keyed by the setting that selects it. Adding an adapter
means adding one factory here; the domain, ports and application do not change (open/closed).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langgraph.types import interrupt

from decksmith.application.data_fetch import FactFetcher
from decksmith.application.graph import build_graph
from decksmith.application.guardrails import NoBareNumbersGuardrail
from decksmith.application.nodes import DeckNodes
from decksmith.application.service import DeckService
from decksmith.application.sql import SqlCompiler
from decksmith.config import Settings
from decksmith.ports import (
    Catalog,
    DataSource,
    IdentityProvider,
    LLMGateway,
    Renderer,
    StateStore,
    TemplateRepository,
    Tracer,
)

Factory = Callable[[Settings], Any]


def _fake_llm(_: Settings) -> LLMGateway:
    from decksmith.adapters.local.fake_llm import FakeLLM

    return FakeLLM()


def _portkey(s: Settings) -> LLMGateway:
    from decksmith.adapters.local.portkey_gateway import PortkeyGateway

    return PortkeyGateway(s.portkey_base_url, s.portkey_config_dir, s.portkey_api_key, env=s.env)


def _duckdb(s: Settings) -> DataSource:
    from decksmith.adapters.local.duckdb_source import DuckDBDataSource

    return DuckDBDataSource(s.duckdb_path)


def _dbsql(s: Settings) -> DataSource:
    from decksmith.adapters.databricks.sql_statements import DatabricksSqlDataSource

    return DatabricksSqlDataSource(s.databricks_host, s.databricks_warehouse_id)


def _memory(_: Settings) -> StateStore:
    from decksmith.adapters.local.state_stores import InMemoryStateStore

    return InMemoryStateStore()


def _postgres(s: Settings) -> StateStore:
    from decksmith.adapters.local.state_stores import PostgresStateStore

    return PostgresStateStore(s.postgres_dsn)


def _noop(_: Settings) -> Tracer:
    from decksmith.adapters.local.tracers import NoopTracer

    return NoopTracer()


def _mlflow(s: Settings) -> Tracer:
    from decksmith.adapters.local.tracers import MlflowTracer

    return MlflowTracer(s.mlflow_tracking_uri, s.mlflow_experiment)


def _static(_: Settings) -> IdentityProvider:
    from decksmith.adapters.local.identity import StaticTokenIdentity

    return StaticTokenIdentity()


def _jwt(s: Settings) -> IdentityProvider:
    from decksmith.adapters.local.identity import JwtIdentity

    if not s.jwt_secret:
        raise ValueError("DECKSMITH_JWT_SECRET is required for identity=jwt")
    return JwtIdentity(s.jwt_secret)


def _apps(_: Settings) -> IdentityProvider:
    from decksmith.adapters.databricks.apps_identity import DatabricksAppsIdentity

    return DatabricksAppsIdentity()


LLMS: dict[str, Factory] = {"fake": _fake_llm, "portkey": _portkey}
SOURCES: dict[str, Factory] = {"duckdb": _duckdb, "databricks": _dbsql}
STATE_STORES: dict[str, Factory] = {"memory": _memory, "postgres": _postgres}
TRACERS: dict[str, Factory] = {"noop": _noop, "mlflow": _mlflow}
IDENTITIES: dict[str, Factory] = {"static": _static, "jwt": _jwt, "databricks_apps": _apps}


def _catalog(s: Settings, source: DataSource) -> Catalog:
    if s.catalog == "unity_catalog":
        from decksmith.adapters.databricks.unity_catalog import UnityCatalogPassthrough

        return UnityCatalogPassthrough(s.databricks_catalog)
    from decksmith.adapters.local.duckdb_source import DuckDBDataSource
    from decksmith.adapters.local.policy_catalog import PerUserViewCatalog

    if not isinstance(source, DuckDBDataSource):
        raise ValueError("per-user-view catalogs need the duckdb data source")
    views: Catalog = PerUserViewCatalog(source.view_exists)
    if s.catalog == "uc_oss":
        from decksmith.adapters.local.uc_oss_catalog import UnityCatalogOssCatalog

        return UnityCatalogOssCatalog(views, s.uc_oss_url)
    return views


def _templates() -> TemplateRepository:
    from decksmith.adapters.local.file_templates import FileTemplateRepository

    return FileTemplateRepository()


def _renderer(s: Settings) -> Renderer:
    from decksmith.adapters.local.pptx_renderer import PptxRenderer

    return PptxRenderer(s.output_dir, s.pptx_template)


@dataclass
class Container:
    settings: Settings
    service: DeckService
    identity: IdentityProvider
    llm: LLMGateway
    state_store: StateStore

    def close(self) -> None:
        self.state_store.close()


def build_container(
    settings: Settings | None = None,
    *,
    llm: LLMGateway | None = None,
    source: DataSource | None = None,
    catalog: Catalog | None = None,
    renderer: Renderer | None = None,
    state_store: StateStore | None = None,
) -> Container:
    """Wire everything. Keyword overrides let tests inject fakes without touching settings."""
    s = settings or Settings()
    llm = llm or LLMS[s.llm](s)
    source = source or SOURCES[s.data_source](s)
    catalog = catalog or _catalog(s, source)
    templates = _templates()
    store = state_store or STATE_STORES[s.state_store](s)
    nodes = DeckNodes(
        llm=NoBareNumbersGuardrail(llm),
        fetcher=FactFetcher(templates, SqlCompiler(catalog, source.dialect), source),
        templates=templates,
        renderer=renderer or _renderer(s),
        tracer=TRACERS[s.tracer](s),
        interrupt=interrupt,
    )
    graph = build_graph(nodes, store.checkpointer())
    return Container(
        settings=s, service=DeckService(graph), identity=IDENTITIES[s.identity](s), llm=llm, state_store=store
    )
