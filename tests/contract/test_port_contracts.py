"""Contract tests: every adapter of a port must honour the same behaviour (Liskov substitution).

Each port has one parametrised fixture listing its offline-constructible adapters; the same
assertions run against all of them. Adding an adapter means adding it to the fixture.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from decksmith.adapters.databricks.apps_identity import DatabricksAppsIdentity
from decksmith.adapters.databricks.sql_statements import DatabricksSqlDataSource
from decksmith.adapters.databricks.unity_catalog import UnityCatalogPassthrough
from decksmith.adapters.local.duckdb_source import DuckDBDataSource
from decksmith.adapters.local.fake_llm import FakeLLM
from decksmith.adapters.local.file_templates import FileTemplateRepository
from decksmith.adapters.local.identity import StaticTokenIdentity
from decksmith.adapters.local.policy_catalog import PerUserViewCatalog
from decksmith.adapters.local.portkey_gateway import PortkeyGateway
from decksmith.adapters.local.pptx_renderer import PptxRenderer
from decksmith.adapters.local.state_stores import InMemoryStateStore
from decksmith.adapters.local.tracers import NoopTracer
from decksmith.domain.deckspec import DeckSpec
from decksmith.domain.errors import AccessDenied, AuthenticationError, UnknownTemplate
from decksmith.domain.facts import FactRegistry
from decksmith.domain.principal import Principal
from decksmith.ports import (
    Catalog,
    DataSource,
    IdentityProvider,
    LLMGateway,
    LLMRequest,
    Message,
    Renderer,
    StateStore,
    TemplateRepository,
    Tracer,
)

CONFIGS = Path(__file__).resolve().parents[2] / "configs" / "portkey"


# --- IdentityProvider ------------------------------------------------------------------
@pytest.fixture(params=["static", "databricks_apps"])
def identity(request: pytest.FixtureRequest) -> tuple[IdentityProvider, dict[str, str]]:
    if request.param == "static":
        return StaticTokenIdentity(), {"Authorization": "Bearer alice-token"}
    return DatabricksAppsIdentity(), {"X-Forwarded-Access-Token": "t", "X-Forwarded-Email": "alice@example.com"}


def test_identity_contract(identity: tuple[IdentityProvider, dict[str, str]]) -> None:
    idp, good = identity
    assert isinstance(idp, IdentityProvider)
    principal = idp.authenticate(good)
    assert principal.user_id and principal.token
    assert principal.token not in repr(principal)
    with pytest.raises(AuthenticationError):
        idp.authenticate({})


# --- Catalog ---------------------------------------------------------------------------
@pytest.fixture(params=["per_user_views", "unity_catalog"])
def catalog(request: pytest.FixtureRequest) -> Catalog:
    if request.param == "per_user_views":
        return PerUserViewCatalog(lambda name: name.endswith("__alice"))
    return UnityCatalogPassthrough()


def test_catalog_contract(catalog: Catalog) -> None:
    assert isinstance(catalog, Catalog)
    ref = catalog.resolve("cs.churn_monthly", Principal(user_id="alice"))
    assert ref.logical == "cs.churn_monthly" and ref.lineage == "main.cs.churn_monthly"
    with contextlib.suppress(AccessDenied):  # local emulation denies; Unity Catalog denies at query time
        catalog.resolve("cs.churn_monthly", Principal(user_id="carol"))


# --- DataSource ------------------------------------------------------------------------
def _dbsql() -> DataSource:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers["authorization"] != "Bearer bob-token":
            return httpx.Response(403)
        return httpx.Response(
            200,
            json={
                "statement_id": "st",
                "status": {"state": "SUCCEEDED"},
                "manifest": {"schema": {"columns": [{"name": "n"}]}},
                "result": {"data_array": [["1"]]},
            },
        )

    return DatabricksSqlDataSource(
        "https://dbc", "wh", httpx.Client(base_url="https://dbc", transport=httpx.MockTransport(handler))
    )


@pytest.fixture(params=["duckdb", "databricks"])
def data_source(request: pytest.FixtureRequest, lakehouse: Path) -> DataSource:
    return DuckDBDataSource(lakehouse) if request.param == "duckdb" else _dbsql()


def test_data_source_contract(data_source: DataSource) -> None:
    assert isinstance(data_source, DataSource) and data_source.dialect in ("duckdb", "databricks")
    result = data_source.execute("SELECT 1 AS n", {}, Principal(user_id="bob", token="bob-token"))
    assert result.columns == ("n",) and float(result.rows[0][0]) == 1.0 and result.statement_id


# --- LLMGateway ------------------------------------------------------------------------
def _portkey() -> LLMGateway:
    def create(**kwargs: Any) -> Any:
        return SimpleNamespace(
            model="m",
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))],
        )

    return PortkeyGateway(
        "http://gw", CONFIGS, client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    )


@pytest.fixture(params=["fake", "portkey"])
def llm(request: pytest.FixtureRequest) -> LLMGateway:
    return FakeLLM() if request.param == "fake" else _portkey()


def test_llm_contract(llm: LLMGateway) -> None:
    assert isinstance(llm, LLMGateway)
    request = LLMRequest(
        node="intake",
        tier="small",
        run_id="r",
        messages=(Message(role="user", content=json.dumps({"request": "Q3 2026 churn"})),),
    )
    response = llm.complete(request)
    assert json.loads(response.text) and response.model


# --- Renderer, StateStore, Tracer, TemplateRepository ------------------------------------
def test_renderer_contract(tmp_path: Path, spec_dict: dict[str, object], facts: FactRegistry) -> None:
    renderer: Renderer = PptxRenderer(tmp_path)
    assert isinstance(renderer, Renderer)
    deck = renderer.render(DeckSpec.model_validate(spec_dict), facts, "contract")
    assert Path(deck.path).exists() and len(deck.sha256) == 64 and deck.slide_count == 5


@pytest.fixture(params=["memory"])
def state_store(request: pytest.FixtureRequest) -> Iterator[StateStore]:
    store = InMemoryStateStore()
    yield store
    store.close()


def test_state_store_contract(state_store: StateStore) -> None:
    assert isinstance(state_store, StateStore)
    saver = state_store.checkpointer()
    assert hasattr(saver, "get_tuple") and hasattr(saver, "put")


def test_tracer_contract() -> None:
    tracer: Tracer = NoopTracer()
    assert isinstance(tracer, Tracer)
    with tracer.span("node", {"run_id": "r"}):
        pass


def test_template_repository_contract() -> None:
    repo: TemplateRepository = FileTemplateRepository()
    assert isinstance(repo, TemplateRepository)
    assert all(repo.get(t.id) == t for t in repo.list())
    with pytest.raises(UnknownTemplate):
        repo.get("nope")
