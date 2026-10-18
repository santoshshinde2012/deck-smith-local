from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import date
from typing import Any

import httpx
import pytest

from decksmith.adapters.databricks.sql_statements import DatabricksSqlDataSource
from decksmith.adapters.databricks.unity_catalog import UnityCatalogPassthrough
from decksmith.adapters.local.file_templates import FileTemplateRepository
from decksmith.application.data_fetch import FactFetcher
from decksmith.application.sql import SqlCompiler
from decksmith.bootstrap import Container
from decksmith.domain.errors import AccessDenied, UpstreamError
from decksmith.domain.facts import FactRegistry
from decksmith.domain.outline import DataRequest
from decksmith.domain.principal import Principal
from tests.conftest import REQUEST

USER = Principal(user_id="bob", token="private-user-token")


def _success(rows: list[list[Any]]) -> dict[str, Any]:
    return {
        "statement_id": "st-1",
        "status": {"state": "SUCCEEDED"},
        "manifest": {
            "schema": {"columns": [{"name": "value"}]},
            "total_chunk_count": 1,
            "total_row_count": len(rows),
            "truncated": False,
        },
        "result": {"data_array": rows, "chunk_index": 0, "row_offset": 0, "row_count": len(rows)},
    }


def _source(handler: Callable[[httpx.Request], httpx.Response], **options: Any) -> DatabricksSqlDataSource:
    return DatabricksSqlDataSource(
        "https://dbc",
        "warehouse",
        httpx.Client(base_url="https://dbc", transport=httpx.MockTransport(handler)),
        poll_interval=0,
        **options,
    )


def test_waits_for_pending_and_running_statements_with_user_token() -> None:
    requests: list[httpx.Request] = []
    responses = [
        {"statement_id": "st-1", "status": {"state": "PENDING"}},
        {"statement_id": "st-1", "status": {"state": "RUNNING"}},
        _success([["0.025"]]),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=responses.pop(0))

    result = _source(handler).execute("SELECT :month", {"month": date(2026, 7, 1)}, USER)
    assert result.rows == ((0.025,),) and result.statement_id == "st-1"
    assert [(r.method, r.url.path) for r in requests] == [
        ("POST", "/api/2.0/sql/statements"),
        ("GET", "/api/2.0/sql/statements/st-1"),
        ("GET", "/api/2.0/sql/statements/st-1"),
    ]
    assert all(r.headers["authorization"] == "Bearer private-user-token" for r in requests)
    body = json.loads(requests[0].content)
    assert body["on_wait_timeout"] == "CONTINUE"
    assert body["parameters"] == [{"name": "month", "value": "2026-07-01", "type": "DATE"}]


def test_pending_statement_stops_after_bounded_polling() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"statement_id": "st-1", "status": {"state": "RUNNING"}})

    with pytest.raises(UpstreamError, match="polling limit"):
        _source(handler, max_poll_attempts=2).execute("SELECT 1", {}, USER)
    assert len(requests) == 3


def test_fetches_every_chunk_even_when_next_pointer_is_missing() -> None:
    first = _success([["1"]])
    first["manifest"].update(total_chunk_count=3, total_row_count=3)
    first["result"]["next_chunk_index"] = 1
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(200, json=first)
        index = int(request.url.path.rsplit("/", 1)[1])
        return httpx.Response(
            200,
            json={"data_array": [[str(index + 1)]], "chunk_index": index, "row_count": 1, "row_offset": index},
        )

    assert _source(handler).execute("SELECT 1", {}, USER).rows == ((1.0,), (2.0,), (3.0,))
    assert [r.url.path for r in requests[1:]] == [
        "/api/2.0/sql/statements/st-1/result/chunks/1",
        "/api/2.0/sql/statements/st-1/result/chunks/2",
    ]
    assert all(r.headers["authorization"] == "Bearer private-user-token" for r in requests)


def test_next_chunk_link_also_indicates_more_results() -> None:
    first = _success([["EU"]])
    del first["manifest"]["total_chunk_count"]
    first["manifest"]["total_row_count"] = 2
    first["result"]["next_chunk_internal_link"] = "/api/2.0/sql/statements/st-1/result/chunks/1"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=first if request.method == "POST" else {"data_array": [[None]], "chunk_index": 1, "row_offset": 1},
        )

    assert _source(handler).execute("SELECT 1", {}, USER).rows == (("EU",), (None,))


def test_schema_preserves_numeric_looking_string_categories() -> None:
    response = _success([["001", "0.024"], ["002", "0.015"]])
    response["manifest"]["schema"]["columns"] = [
        {"name": "segment", "type_name": "STRING"},
        {"name": "churn_rate", "type_text": "DECIMAL(12, 6)"},
    ]
    result = _source(lambda _: httpx.Response(200, json=response)).execute("SELECT 1", {}, USER)
    assert result.columns == ("segment", "churn_rate")
    assert result.rows == (("001", 0.024), ("002", 0.015))


@pytest.mark.parametrize("include_chunk", [True, False])
def test_empty_result_manifest_is_valid(include_chunk: bool) -> None:
    response = _success([])
    response["manifest"]["total_chunk_count"] = 0
    if not include_chunk:
        del response["result"]
    assert _source(lambda _: httpx.Response(200, json=response)).execute("SELECT 1", {}, USER).rows == ()


def test_truncated_result_is_refused_before_any_fact_is_created() -> None:
    response = _success([["1"]])
    response["manifest"]["truncated"] = True
    with pytest.raises(UpstreamError, match="truncated"):
        _source(lambda _: httpx.Response(200, json=response)).execute("SELECT 1", {}, USER)


@pytest.mark.parametrize(
    "change",
    [
        {"row_count": 2},
        {"row_offset": 1},
        {"chunk_index": 1},
        {"data_array": [["1", "extra"]]},
        {"next_chunk_index": 0},
        {"external_links": [{"external_link": "https://storage.example/result"}]},
    ],
)
def test_inconsistent_chunks_never_produce_partial_results(change: dict[str, Any]) -> None:
    response = _success([["1"]])
    response["result"].update(change)
    with pytest.raises(UpstreamError):
        _source(lambda _: httpx.Response(200, json=response)).execute("SELECT 1", {}, USER)


def test_manifest_row_count_mismatch_is_refused() -> None:
    response = _success([["1"]])
    response["manifest"]["total_row_count"] = 2
    with pytest.raises(UpstreamError, match="incomplete"):
        _source(lambda _: httpx.Response(200, json=response)).execute("SELECT 1", {}, USER)


def test_chunk_pointer_beyond_the_manifest_is_refused() -> None:
    response = _success([["1"]])
    response["result"]["next_chunk_index"] = 1
    with pytest.raises(UpstreamError, match="more chunks"):
        _source(lambda _: httpx.Response(200, json=response)).execute("SELECT 1", {}, USER)


def test_unexpected_result_format_is_refused() -> None:
    response = _success([["1"]])
    response["manifest"]["format"] = "ARROW_STREAM"
    with pytest.raises(UpstreamError, match="unsupported result format"):
        _source(lambda _: httpx.Response(200, json=response)).execute("SELECT 1", {}, USER)


@pytest.mark.parametrize("stage", ["submit", "poll", "chunk"])
def test_http_permission_denials_at_every_stage_are_access_denied(stage: str) -> None:
    response = _success([["1"]])
    response["manifest"].update(total_chunk_count=2, total_row_count=2)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and stage != "submit":
            return httpx.Response(
                200, json={"statement_id": "st-1", "status": {"state": "PENDING"}} if stage == "poll" else response
            )
        return httpx.Response(403, text="private upstream details")

    with pytest.raises(AccessDenied) as error:
        _source(handler).execute("SELECT 1", {}, USER)
    assert "private" not in str(error.value)


@pytest.mark.parametrize(
    "status",
    [
        {"error": {"error_code": "INSUFFICIENT_PERMISSIONS"}},
        {"error": {"error_code": "INSUFFICIENT_PRIVILEGES"}},
        {"error": {"error_code": "PERMISSION_DENIED"}},
        {"sql_state": "42501", "error": {"error_code": "BAD_REQUEST"}},
        {"error": {"sql_state": "42501", "error_code": "BAD_REQUEST"}},
        {"error": {"error_code": "BAD_REQUEST", "message": "[INSUFFICIENT_PERMISSIONS] SELECT denied"}},
    ],
)
def test_failed_statement_permission_errors_are_access_denied(status: dict[str, Any]) -> None:
    response = {"statement_id": "st-1", "status": {"state": "FAILED", **status}}
    with pytest.raises(AccessDenied):
        _source(lambda _: httpx.Response(200, json=response)).execute("SELECT 1", {}, USER)


@pytest.mark.parametrize("state", ["FAILED", "CANCELED", "CLOSED"])
def test_other_terminal_errors_remain_failures(state: str) -> None:
    response = {
        "statement_id": "st-1",
        "status": {"state": state, "error": {"error_code": "BAD_REQUEST", "message": "SQL syntax error"}},
    }
    with pytest.raises(UpstreamError, match=state):
        _source(lambda _: httpx.Response(200, json=response)).execute("SELECT 1", {}, USER)


@pytest.mark.parametrize("status", [401, 429, 500])
def test_other_http_errors_remain_failures(status: int) -> None:
    with pytest.raises(UpstreamError):
        _source(lambda _: httpx.Response(status)).execute("SELECT 1", {}, USER)


def test_transport_failure_is_an_upstream_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private connection detail", request=request)

    with pytest.raises(UpstreamError, match="request failed"):
        _source(handler).execute("SELECT 1", {}, USER)


@pytest.mark.parametrize("response", [{}, [], {"statement_id": "st-1", "status": {"state": "SUCCEEDED"}}])
def test_malformed_statement_responses_fail_closed(response: Any) -> None:
    with pytest.raises(UpstreamError):
        _source(lambda _: httpx.Response(200, json=response)).execute("SELECT 1", {}, USER)


def test_missing_result_data_is_not_reported_as_no_rows() -> None:
    response = _success([["1"]])
    del response["result"]
    with pytest.raises(UpstreamError, match="no result data"):
        _source(lambda _: httpx.Response(200, json=response)).execute("SELECT 1", {}, USER)


def test_fact_source_preserves_the_executed_query_and_normalized_parameters() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_success([["0.024"]]))

    templates = FileTemplateRepository()
    fetcher = FactFetcher(templates, SqlCompiler(UnityCatalogPassthrough(), "databricks"), _source(handler))
    registry = FactRegistry()
    fact = fetcher.fetch(
        DataRequest(
            template_id="churn_rate_quarter",
            label="Churn",
            params={"start_month": "2026-07-01", "end_month": "2026-10-01"},
        ),
        USER,
        registry,
    )
    assert fact is not None and fact.value == 0.024
    submitted = json.loads(requests[0].content)
    assert fact.source.sql == submitted["statement"]
    assert fact.source.params == {item["name"]: item["value"] for item in submitted["parameters"]}
    assert fact.source.template_sha256 == hashlib.sha256(templates.get("churn_rate_quarter").sql.encode()).hexdigest()
    assert "private-user-token" not in json.dumps(registry.dump())


def test_all_execution_permission_denials_end_in_a_plain_no_data_refusal(
    make_container: Callable[..., Container], bob: Principal
) -> None:
    source = _source(
        lambda _: httpx.Response(
            200,
            json={
                "statement_id": "st-1",
                "status": {"state": "FAILED", "error": {"error_code": "INSUFFICIENT_PERMISSIONS"}},
            },
        )
    )
    container = make_container(source=source, catalog=UnityCatalogPassthrough())
    run = container.service.start(REQUEST, bob)
    result = container.service.decide(run.run_id, "approve", bob)
    assert result.status == "no_data" and result.artifact is None
    assert result.error and "None of the requested data is visible to you" in result.error
