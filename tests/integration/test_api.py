from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from decksmith.bootstrap import Container
from decksmith.interfaces.api import create_app
from tests.conftest import REQUEST

pytestmark = pytest.mark.integration

BOB = {"Authorization": "Bearer bob-token"}
ALICE = {"Authorization": "Bearer alice-token"}


@pytest.fixture
def client(make_container: Callable[..., Container]) -> TestClient:
    return TestClient(create_app(make_container()))


def test_health(client: TestClient) -> None:
    body = client.get("/healthz").json()
    assert body["ok"] and body["adapters"]["llm"] == "fake"


def test_full_flow_and_download(client: TestClient) -> None:
    run = client.post("/v1/decks", json={"request": REQUEST}, headers=BOB).json()
    assert run["status"] == "awaiting_approval"
    assert client.get(f"/v1/decks/{run['run_id']}/file", headers=BOB).status_code == 409
    done = client.post(f"/v1/decks/{run['run_id']}/decision", json={"action": "approve"}, headers=BOB).json()
    assert done["status"] == "done"
    file = client.get(f"/v1/decks/{run['run_id']}/file", headers=BOB)
    assert file.status_code == 200 and file.content[:2] == b"PK"


def test_auth_and_ownership(client: TestClient) -> None:
    assert client.post("/v1/decks", json={"request": REQUEST}).status_code == 401
    run = client.post("/v1/decks", json={"request": REQUEST}, headers=BOB).json()
    assert client.get(f"/v1/decks/{run['run_id']}", headers=ALICE).status_code == 404  # not "forbidden"
    assert client.get("/v1/decks/nope", headers=BOB).status_code == 404


def test_responses_endpoint(client: TestClient) -> None:
    first = client.post("/responses", headers=BOB, json={"input": [{"role": "user", "content": REQUEST}]}).json()
    run_id = first["custom_outputs"]["run_id"]
    assert first["custom_outputs"]["status"] == "awaiting_approval"
    assert "Proposed outline" in first["output"][0]["content"][0]["text"]
    second = client.post(
        "/responses",
        headers=BOB,
        json={
            "input": [{"role": "user", "content": "approve"}],
            "custom_inputs": {"run_id": run_id, "action": "approve"},
        },
    ).json()
    assert second["custom_outputs"]["status"] == "done"
