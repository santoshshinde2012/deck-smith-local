"""E1-E11 from the DeckSmith local-development test plan (see README), run offline with the fake LLM.

E1-E8 run here. Parts that need running services are marked `stack` and skip without `make up`.
E9-E11 need a Databricks workspace or staging and are skipped with the reason.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from decksmith.adapters.local.fake_llm import FakeLLM
from decksmith.adapters.local.pptx_renderer import PptxRenderer
from decksmith.adapters.local.state_stores import InMemoryStateStore
from decksmith.application.guardrails import NoBareNumbersGuardrail
from decksmith.bootstrap import Container
from decksmith.domain.deckspec import DeckSpec
from decksmith.domain.errors import GuardrailViolation
from decksmith.domain.facts import FactRegistry
from decksmith.domain.integrity import chart_consistency, numeric_integrity
from decksmith.domain.principal import Principal
from decksmith.evaluation.harness import load_golden, make_predict, run_mlflow, run_plain
from tests.conftest import REQUEST

pytestmark = pytest.mark.e2e


def _stack_up(url: str) -> bool:
    try:
        return httpx.get(url, timeout=1).status_code < 500
    except httpx.HTTPError:
        return False


def _approve(container: Container, principal: Principal, request: str = REQUEST):  # type: ignore[no-untyped-def]
    view = container.service.start(request, principal)
    assert view.status == "awaiting_approval"
    return container.service.decide(view.run_id, "approve", principal)


# E1 -------------------------------------------------------------------------------------
def test_e1_renderer_golden(tmp_path: Path, spec_dict: dict[str, object], facts: FactRegistry) -> None:
    """Same spec + template => identical slide XML. (Zip bytes differ by timestamps, so we compare XML.)"""
    spec = DeckSpec.model_validate(spec_dict)
    hashes = {PptxRenderer(tmp_path / str(i)).render(spec, facts, "golden").content_hash for i in range(3)}
    assert len(hashes) == 1
    spec_dict["slides"][3]["bullets"] = ["word " * 30] * 6  # type: ignore[index]
    assert PptxRenderer(tmp_path / "o").render(DeckSpec.model_validate(spec_dict), facts, "o").overflow_slides == (
        "s04",
    )


# E2 -------------------------------------------------------------------------------------
def test_e2_numeric_integrity_on_produced_deck(container: Container, bob: Principal) -> None:
    view = _approve(container, bob)
    spec, registry = DeckSpec.model_validate(view.spec), FactRegistry.load(view.facts)
    assert numeric_integrity(spec, registry) == [] and chart_consistency(spec, registry) == []
    chart_fact = next(f for f in registry.all() if f.source.template_id == "churn_trend_monthly")
    assert len(chart_fact.values) == 3  # one point per month of the quarter


# E3 -------------------------------------------------------------------------------------
def test_e3_resume_after_restart_shared_checkpointer(make_container: Callable[..., Container], bob: Principal) -> None:
    """A fresh container (new graph, new service) resumes the run from the same checkpoint store."""
    store = InMemoryStateStore()
    first = make_container(state_store=store)
    run = first.service.start(REQUEST, bob)
    del first
    second = make_container(state_store=store)
    assert second.service.decide(run.run_id, "approve", bob).status == "done"


@pytest.mark.stack
def test_e3_resume_after_restart_postgres(make_container: Callable[..., Container], bob: Principal) -> None:
    dsn = os.environ.get("DECKSMITH_POSTGRES_DSN", "postgresql://decksmith:decksmith@localhost:5433/decksmith")
    try:
        from decksmith.adapters.local.state_stores import PostgresStateStore

        store_a = PostgresStateStore(dsn)
    except Exception as exc:
        pytest.skip(f"Postgres not reachable ({type(exc).__name__}); run `make up`")
    run = make_container(state_store=store_a).service.start(REQUEST, bob)
    store_a.close()
    store_b = PostgresStateStore(dsn)
    try:
        assert make_container(state_store=store_b).service.decide(run.run_id, "approve", bob).status == "done"
    finally:
        store_b.close()


def test_e3_edit_and_reject_routes(container: Container, bob: Principal) -> None:
    run = container.service.start(REQUEST, bob)
    edited = container.service.decide(run.run_id, "edit", bob, "drop the segment slide")
    assert edited.status == "awaiting_approval"
    assert [s["slide_id"] for s in edited.outline["slides"]] == ["s01", "s02", "s03", "s05"]  # type: ignore[index]
    assert container.service.decide(run.run_id, "reject", bob).status == "rejected"


# E4 -------------------------------------------------------------------------------------
def test_e4_request_to_pptx(container: Container, bob: Principal) -> None:
    view = _approve(container, bob)
    assert view.status == "done" and view.issues == []
    assert Path(view.artifact["path"]).exists() and view.artifact["slide_count"] == 5  # type: ignore[index]
    assert {f["source"]["template_id"] for f in view.facts} == {
        "churn_rate_quarter",
        "nrr_quarter",
        "active_subscriptions",
        "churn_trend_monthly",
        "churn_by_segment",
    }
    assert all(f["source"]["tables"][0].startswith("main.cs.") for f in view.facts)  # governed lineage names


def test_e4_qa_loop_recovers(make_container: Callable[..., Container], bob: Principal) -> None:
    llm = FakeLLM({"writer": ["invalid_json", "unknown_fact"]})
    view = _approve(make_container(llm=llm), bob)
    assert view.status == "done" and llm.calls["writer"] == 3 and view.schema_valid_first_try is False


def test_e4_qa_loop_gives_up(make_container: Callable[..., Container], bob: Principal) -> None:
    llm = FakeLLM({"writer": ["unknown_fact"] * 5})
    view = _approve(make_container(llm=llm), bob)
    assert view.status == "failed" and llm.calls["writer"] == 3 and view.artifact is None


# E5 -------------------------------------------------------------------------------------
def test_e5_permissions(container: Container, alice: Principal, bob: Principal, carol: Principal) -> None:
    a, b = _approve(container, alice), _approve(container, bob)
    actives = {
        v.run_id: next(f["value"] for f in v.facts if f["source"]["template_id"] == "active_subscriptions")
        for v in (a, b)
    }
    assert 0 < actives[a.run_id] < actives[b.run_id]  # alice sees her region only
    c = _approve(container, carol)
    assert c.status == "no_data" and c.artifact is None and "visible to you" in c.error


# E6 -------------------------------------------------------------------------------------
def test_e6_guardrail_returns_446(make_container: Callable[..., Container], bob: Principal) -> None:
    with pytest.raises(GuardrailViolation) as err:
        from tests.unit.test_guardrail_and_fake_llm import _writer_request

        NoBareNumbersGuardrail(FakeLLM({"writer": ["bare_digit"]})).complete(_writer_request())
    assert err.value.status_code == 446
    llm = FakeLLM({"writer": ["bare_digit"]})
    view = _approve(make_container(llm=llm), bob)  # the graph treats a 446 as a QA issue and rewrites
    assert view.status == "done" and llm.calls["writer"] == 2


@pytest.mark.stack
def test_e6_portkey_gateway_up() -> None:
    if not _stack_up("http://localhost:8787/"):
        pytest.skip("Portkey gateway not running; run `make up`")
    assert httpx.get("http://localhost:8787/", timeout=5).status_code < 500


# E7 -------------------------------------------------------------------------------------
def test_e7_golden_set_plain(make_container: Callable[..., Container]) -> None:
    summary = run_plain(load_golden(), make_predict(make_container().service))["summary"]
    assert all(v == 1.0 for v in summary.values()), summary


def test_e7_golden_set_mlflow(make_container: Callable[..., Container], tmp_path: Path) -> None:
    import mlflow

    mlflow.set_tracking_uri(f"sqlite:///{tmp_path / 'mlflow.db'}")
    mlflow.set_experiment("decksmith-e7")
    result = run_mlflow(load_golden()[:3], make_predict(make_container().service))
    gates = {k: v for k, v in result.metrics.items() if k.endswith("/mean")}
    assert gates and all(v == 1.0 for v in gates.values()), result.metrics


# E8 -------------------------------------------------------------------------------------
def test_e8_tokens_per_node(container: Container, bob: Principal) -> None:
    view = _approve(container, bob)
    nodes = [u["node"] for u in view.usage]
    assert nodes == ["intake", "planner", "writer"]
    assert all(u["prompt_tokens"] > 0 and u["completion_tokens"] > 0 for u in view.usage)


# E9-E11 -------------------------------------------------------------------------------
@pytest.mark.skip(reason="E9 needs a Databricks workspace (Databricks Connect, Genie space): tier L3")
def test_e9_databricks_sql_parity() -> None: ...


@pytest.mark.skip(reason="E10 needs UC row filters, an App with user_api_scopes and Lakebase: tier L3")
def test_e10_real_obo() -> None: ...


@pytest.mark.skip(reason="E11 needs the staging workspace (PrivateLink, NCC, Portkey hybrid): tier L4")
def test_e11_staging_controls() -> None: ...
