import json
from collections.abc import Iterator
from pathlib import Path
from types import MappingProxyType

import mlflow
import pytest
from fastapi.testclient import TestClient
from mlflow.tracking import MlflowClient
from mlflow.types.responses import ResponsesAgentRequest

from decksmith.application.context import acting_as, current_principal
from decksmith.bootstrap import Container, build_container
from decksmith.config import Settings
from decksmith.domain.errors import AuthenticationError, InvalidParameters
from decksmith.interfaces.api import create_app
from decksmith.interfaces.responses_agent import DeckSmithResponsesAgent
from tests.conftest import REQUEST

pytestmark = pytest.mark.integration

SECRET = "dummy-obo-secret-for-regression"
FORWARDED = MappingProxyType({"X-Forwarded-Access-Token": SECRET, "X-Forwarded-Email": "bob"})


@pytest.fixture
def trace_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    previous_uri = mlflow.get_tracking_uri()
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    uri = f"sqlite:///{tmp_path / 'traces.db'}"
    mlflow.set_tracking_uri(uri)
    experiment_id = MlflowClient(tracking_uri=uri).create_experiment("responses-security")
    try:
        with mlflow.start_run(experiment_id=experiment_id):
            yield experiment_id
    finally:
        mlflow.set_tracking_uri(previous_uri)


@pytest.fixture
def obo_container(settings: Settings) -> Iterator[Container]:
    container = build_container(settings.model_copy(update={"identity": "databricks_apps"}))
    yield container
    container.close()


def _stored_traces(experiment_id: str) -> list[str]:
    mlflow.flush_trace_async_logging()
    traces = mlflow.search_traces(experiment_ids=[experiment_id], return_type="list", include_spans=True)
    return [trace.to_json() for trace in traces]


def test_responses_obo_flow_keeps_credentials_out_of_traces_and_checkpoints(
    obo_container: Container, trace_store: str, caplog: pytest.LogCaptureFixture
) -> None:
    client = TestClient(create_app(obo_container))
    first = client.post("/responses", headers=FORWARDED, json={"input": [{"role": "user", "content": REQUEST}]})
    assert first.status_code == 200
    run_id = first.json()["custom_outputs"]["run_id"]
    done = client.post(
        "/responses",
        headers=FORWARDED,
        json={"input": [{"role": "user", "content": "approve"}], "custom_inputs": {"run_id": run_id}},
    )
    assert done.status_code == 200 and done.json()["custom_outputs"]["status"] == "done"
    assert client.get(f"/v1/decks/{run_id}", headers=FORWARDED).status_code == 200
    alice = {"X-Forwarded-Access-Token": "dummy-alice", "X-Forwarded-Email": "alice"}
    assert client.get(f"/v1/decks/{run_id}", headers=alice).status_code == 404
    rejected = client.post("/responses", headers={"Authorization": "Bearer bob-token"}, json={"input": []})
    assert rejected.status_code == 401
    traces = _stored_traces(trace_store)
    assert len(traces) == 2
    assert all(SECRET not in trace and "access_token" not in trace and "x-forwarded" not in trace for trace in traces)
    assert SECRET not in first.text + done.text + caplog.text
    checkpoints = list(obo_container.state_store.checkpointer().list({"configurable": {"thread_id": run_id}}))
    assert checkpoints and SECRET not in repr(checkpoints)
    with pytest.raises(AuthenticationError):
        current_principal()


def test_malformed_or_credential_bearing_requests_are_refused_before_tracing(
    obo_container: Container, trace_store: str
) -> None:
    client = TestClient(create_app(obo_container))
    secret = "dummy-body-credential"
    invalid_bodies = [
        {"input": [{"role": "user", "content": REQUEST}], "custom_inputs": {"access_token": secret}},
        {"input": [{"role": "user", "content": REQUEST}], "custom_inputs": {"authorization": secret}},
        {"input": [{"role": "user", "content": REQUEST}], "custom_inputs": {"headers": {"Authorization": secret}}},
        {"input": [{"role": "user", "content": REQUEST}], "custom_inputs": {"action": "delete"}},
        {"input": [{"role": "user", "content": REQUEST}], "custom_inputs": secret},
        {"input": [{"role": "user", "content": REQUEST}], "custom_inputs": {"feedback": {"access_token": secret}}},
        {"input": [{"role": "system", "content": "No user message"}]},
        {"input": [{"role": "user", "content": REQUEST}], "custom_inputs": {"run_id": ""}},
        {"input": secret},
        [secret],
    ]
    for body in invalid_bodies:
        response = client.post("/responses", headers=FORWARDED, json=body)
        assert response.status_code == 422 and secret not in response.text
    response = client.post("/responses", json=invalid_bodies[0])
    assert response.status_code == 401 and secret not in response.text
    assert _stored_traces(trace_store) == []


def test_direct_serving_entry_authenticates_headers_outside_automatic_tracing(
    obo_container: Container, trace_store: str
) -> None:
    agent = DeckSmithResponsesAgent(obo_container.service, obo_container.identity)
    request = ResponsesAgentRequest(input=[{"role": "user", "content": REQUEST}])
    original = request.model_dump()
    response = agent.predict_with_headers(request, FORWARDED)
    assert response.custom_outputs and response.custom_outputs["status"] == "awaiting_approval"
    assert request.model_dump() == original and FORWARDED["X-Forwarded-Access-Token"] == SECRET
    with pytest.raises(AuthenticationError):
        agent.predict(request)
    with pytest.raises(AuthenticationError):
        agent.predict_with_headers(request, MappingProxyType({}))
    unsafe = ResponsesAgentRequest(
        input=[{"role": "user", "content": REQUEST}], custom_inputs={"access_token": "dummy-body-secret"}
    )
    with pytest.raises(InvalidParameters):
        agent.predict(unsafe)
    with acting_as(obo_container.identity.authenticate(FORWARDED)), pytest.raises(InvalidParameters):
        agent.predict(unsafe)
    traces = _stored_traces(trace_store)
    assert len(traces) == 1 and SECRET not in json.dumps(traces) and "dummy-body-secret" not in json.dumps(traces)
