import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import jwt
import pytest

from decksmith.adapters.databricks.apps_identity import DatabricksAppsIdentity
from decksmith.adapters.databricks.sql_statements import DatabricksSqlDataSource
from decksmith.adapters.databricks.unity_catalog import UnityCatalogPassthrough
from decksmith.adapters.local.identity import JwtIdentity, StaticTokenIdentity
from decksmith.adapters.local.policy_catalog import PerUserViewCatalog
from decksmith.adapters.local.portkey_gateway import PortkeyGateway
from decksmith.adapters.local.uc_oss_catalog import UnityCatalogOssCatalog
from decksmith.domain.errors import AccessDenied, AuthenticationError
from decksmith.domain.principal import Principal
from decksmith.ports import Catalog, DataSource, IdentityProvider, LLMGateway, LLMRequest, Message

CONFIGS = Path(__file__).resolve().parents[2] / "configs" / "portkey"


def test_static_identity() -> None:
    idp = StaticTokenIdentity()
    assert idp.authenticate({"Authorization": "Bearer alice-token"}).user_id == "alice"
    for headers in ({}, {"Authorization": "Bearer nope"}):
        with pytest.raises(AuthenticationError):
            idp.authenticate(headers)


def test_jwt_identity() -> None:
    token = jwt.encode({"sub": "alice", "aud": "decksmith", "groups": ["eu"]}, "s" * 32, algorithm="HS256")
    principal = JwtIdentity("s" * 32).authenticate({"authorization": f"Bearer {token}"})
    assert principal.user_id == "alice" and principal.groups == ("eu",)
    with pytest.raises(AuthenticationError):
        JwtIdentity("x" * 32).authenticate({"authorization": f"Bearer {token}"})


def test_apps_identity_requires_forwarded_token() -> None:
    principal = DatabricksAppsIdentity().authenticate({"X-Forwarded-Access-Token": "t", "X-Forwarded-Email": "a@x.eu"})
    assert principal.user_id == "a@x.eu" and principal.token == "t"
    assert "t" not in repr(principal)  # token never printed
    with pytest.raises(AuthenticationError):
        DatabricksAppsIdentity().authenticate({"Authorization": "Bearer t"})


def test_per_user_view_catalog() -> None:
    catalog = PerUserViewCatalog(lambda name: name == "lake.cs.v_churn_monthly__alice")
    assert catalog.resolve("cs.churn_monthly", Principal(user_id="alice")).lineage == "main.cs.churn_monthly"
    with pytest.raises(AccessDenied):
        catalog.resolve("cs.churn_monthly", Principal(user_id="carol"))


def test_uc_oss_catalog_checks_registration() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200 if request.url.path.endswith("main.cs.churn_monthly") else 404, json={})

    inner = PerUserViewCatalog(lambda _: True)
    catalog = UnityCatalogOssCatalog(
        inner, "http://uc", client=httpx.Client(base_url="http://uc", transport=httpx.MockTransport(handler))
    )
    assert catalog.resolve("cs.churn_monthly", Principal(user_id="bob")).physical.endswith("__bob")
    with pytest.raises(AccessDenied):
        catalog.resolve("cs.unknown", Principal(user_id="bob"))


def test_databricks_sql_uses_user_token() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "statement_id": "st-1",
                "status": {"state": "SUCCEEDED"},
                "manifest": {"schema": {"columns": [{"name": "churn_rate"}]}},
                "result": {"data_array": [["0.0236"]]},
            },
        )

    source = DatabricksSqlDataSource(
        "https://dbc", "wh1", httpx.Client(base_url="https://dbc", transport=httpx.MockTransport(handler))
    )
    result = source.execute("SELECT 1", {"start_month": "2026-07-01"}, Principal(user_id="a", token="user-tok"))
    assert seen["auth"] == "Bearer user-tok" and seen["body"]["warehouse_id"] == "wh1"
    assert result.rows == ((0.0236,),) and result.statement_id == "st-1"


def test_databricks_sql_403_is_access_denied() -> None:
    client = httpx.Client(base_url="https://dbc", transport=httpx.MockTransport(lambda r: httpx.Response(403)))
    with pytest.raises(AccessDenied):
        DatabricksSqlDataSource("https://dbc", "wh1", client).execute("SELECT 1", {}, Principal(user_id="a", token="t"))


def test_uc_passthrough() -> None:
    ref = UnityCatalogPassthrough().resolve("cs.churn_monthly", Principal(user_id="a"))
    assert ref.physical == ref.lineage == "main.cs.churn_monthly"


def test_portkey_gateway_sends_inline_config_and_metadata() -> None:
    captured: dict[str, Any] = {}

    def create(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return SimpleNamespace(
            model="llama3.1:8b",
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))],
        )

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    gateway = PortkeyGateway("http://localhost:8787", CONFIGS, client=client)
    response = gateway.complete(
        LLMRequest(
            node="planner", tier="small", run_id="r1", user_hash="h", messages=(Message(role="user", content="hi"),)
        )
    )
    headers = captured["extra_headers"]
    assert json.loads(headers["x-portkey-config"])["strategy"]["mode"] == "fallback"
    assert json.loads(headers["x-portkey-metadata"]) == {
        "_user": "h",
        "app": "decksmith",
        "env": "local",
        "run_id": "r1",
        "node": "planner",
    }
    assert response.prompt_tokens == 10


def test_adapters_satisfy_ports() -> None:
    """Liskov: local and Databricks adapters are interchangeable behind the same Protocols."""
    assert isinstance(StaticTokenIdentity(), IdentityProvider) and isinstance(
        DatabricksAppsIdentity(), IdentityProvider
    )
    assert isinstance(UnityCatalogPassthrough(), Catalog) and isinstance(PerUserViewCatalog(lambda _: True), Catalog)
    assert isinstance(DatabricksSqlDataSource("https://x", "w"), DataSource)
    assert isinstance(PortkeyGateway("http://x", CONFIGS, client=object()), LLMGateway)
