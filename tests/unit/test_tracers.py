"""MLflow tracer: one trace per graph invocation, nested spans, and no credentials."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import mlflow
import pytest
from mlflow.entities import Span

from decksmith.adapters.local.fake_llm import FakeLLM
from decksmith.adapters.local.tracers import MlflowTracer, NoopTracer, sanitize
from decksmith.application.trace_records import fact_record, invocation_output, outline_record
from decksmith.bootstrap import build_container
from decksmith.config import Settings
from decksmith.domain.principal import Principal
from tests.conftest import REQUEST


@pytest.fixture
def tracking(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    previous = mlflow.get_tracking_uri()
    uri = f"sqlite:///{tmp_path / 'traces.db'}"
    mlflow.set_tracking_uri(uri)
    try:
        yield uri
    finally:
        mlflow.set_tracking_uri(previous)


def test_sanitize_drops_secrets_and_clips_long_text() -> None:
    nested: object = "leaf"
    for _ in range(8):
        nested = {"level": nested}
    payload = sanitize(
        {
            "request": "y" * 1600,
            "token": "bob-token",
            "api_key": "sk",
            "nested": {"access_token": "secret", "label": "kept", "user_secret": "no"},
            "items": list(range(50)),
            "count": 3,
            "password": "nope",
            "deep": nested,
            "other": object(),
        }
    )
    assert "token" not in payload
    assert "api_key" not in payload
    assert "password" not in payload
    assert "access_token" not in payload["nested"]
    assert "user_secret" not in payload["nested"]
    assert payload["nested"]["label"] == "kept"
    assert payload["request"].endswith("...") and len(payload["request"]) == 1500
    assert len(payload["items"]) == 40
    assert payload["count"] == 3
    assert payload["deep"]["level"]["level"]["level"]["level"]["level"]["level"] == "..."
    assert isinstance(payload["other"], str)


def test_trace_records_cover_refusals_and_series() -> None:
    assert outline_record(None) is None
    series = fact_record(
        {
            "id": "f4",
            "label": "Monthly churn",
            "kind": "series",
            "format": "nope",
            "categories": ["Jul"],
            "values": [0.02],
            "source": {"template_id": "churn_trend_monthly"},
        }
    )
    assert series["points"] == 1 and series["categories"] == ["Jul"]
    scalar = fact_record(
        {"id": "f1", "label": "Churn", "kind": "scalar", "value": 0.024, "format": "pct1", "source": {}}
    )
    assert scalar["display"] == "2.4%"
    plain = fact_record({"id": "f2", "label": "Count", "kind": "scalar", "value": 1.2, "format": "nope"})
    assert plain["display"] == "1.20"

    payload = invocation_output(
        SimpleNamespace(
            run_id="r",
            status="no_data",
            outline=None,
            spec=None,
            artifact=None,
            error="None of the requested data is visible to you, so no deck was produced.",
            issues=["one"],
        )
    )
    assert payload["error"].startswith("None of the requested")
    assert payload["issues"] == ["one"]
    assert "outline" not in payload and "spec" not in payload


def test_mlflow_span_drops_secret_attributes(tracking: str) -> None:
    tracer = MlflowTracer(tracking, "attr-test")
    with tracer.span("draft", {"token": "bob-token", "run_id": "r"}, span_type="WORKFLOW") as span:
        span.set_attribute("api_key", "sk-test")
        span.set_attribute("run_id", "r")
        span.set_inputs({"request": "hello"})
        span.set_outputs({"status": "ok"})
    mlflow.flush_trace_async_logging()
    experiment = mlflow.get_experiment_by_name("attr-test")
    assert experiment is not None
    traces = mlflow.search_traces(experiment_ids=[experiment.experiment_id], return_type="list", include_spans=True)
    stored = json.dumps([trace.to_json() for trace in traces])
    assert "bob-token" not in stored and "sk-test" not in stored
    assert "hello" in stored


def test_noop_span_accepts_inputs_without_recording() -> None:
    with NoopTracer().span("draft", {"run_id": "r"}, span_type="WORKFLOW") as span:
        span.set_inputs({"token": "bob-token"})
        span.set_outputs({"status": "ok"})
        span.set_attribute("api_key", "sk-test")


def _spans(trace: object) -> list[Span]:
    return list(trace.data.spans)  # type: ignore[attr-defined]


def test_a_run_is_two_traces_with_a_span_tree(tracking: str, lakehouse: Path, tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        duckdb_path=lakehouse,
        output_dir=tmp_path / "out",
        tracer="mlflow",
        mlflow_tracking_uri=tracking,
        mlflow_experiment="decksmith-trace-test",
    )
    bob = Principal(user_id="bob", display_name="Bob", token="bob-token")
    container = build_container(settings, llm=FakeLLM())
    try:
        draft = container.service.start(REQUEST, bob)
        assert draft.status == "awaiting_approval"
        done = container.service.decide(draft.run_id, "approve", bob)
        assert done.status == "done"
        mlflow.flush_trace_async_logging()
        experiment = mlflow.get_experiment_by_name("decksmith-trace-test")
        assert experiment is not None
        traces = mlflow.search_traces(experiment_ids=[experiment.experiment_id], return_type="list", include_spans=True)
    finally:
        container.close()

    assert len(traces) == 2
    by_root = {next(span.name for span in _spans(trace) if span.parent_id is None): trace for trace in traces}
    assert set(by_root) == {"draft", "decision"}

    draft_spans = _spans(by_root["draft"])
    draft_names = {span.name for span in draft_spans}
    assert {"draft", "intake", "intake.model", "planner", "planner.model", "await_approval"} <= draft_names
    draft_root = next(span for span in draft_spans if span.name == "draft")
    assert draft_root.span_type == "WORKFLOW"
    assert draft_root.inputs is not None and draft_root.inputs["request"] == REQUEST
    assert draft_root.inputs["user_id"] == "bob"
    assert "token" not in draft_root.inputs
    assert by_root["draft"].info.request_preview and REQUEST in by_root["draft"].info.request_preview
    intake = next(span for span in draft_spans if span.name == "intake")
    assert intake.parent_id == draft_root.span_id
    assert intake.span_type == "CHAIN"
    model = next(span for span in draft_spans if span.name == "intake.model")
    assert model.parent_id == intake.span_id and model.span_type == "CHAT_MODEL"
    assert model.inputs is not None and model.inputs["messages"][0]["role"] == "system"

    decision_spans = _spans(by_root["decision"])
    decision_names = {span.name for span in decision_spans}
    assert {
        "decision",
        "await_approval",
        "data_fetch",
        "query.churn_rate_quarter",
        "writer",
        "writer.model",
        "guardrail",
        "check",
        "render",
    } <= decision_names
    decision_root = next(span for span in decision_spans if span.name == "decision")
    assert decision_root.inputs is not None and decision_root.inputs["action"] == "approve"
    assert decision_root.outputs is not None and decision_root.outputs["status"] == "done"
    assert decision_root.outputs["deck"]["slide_count"] == 5
    query = next(span for span in decision_spans if span.name == "query.churn_rate_quarter")
    assert query.span_type == "RETRIEVER"
    assert query.inputs is not None and query.inputs["params"]["start_month"] == "2026-07-01"
    data_fetch = next(span for span in decision_spans if span.name == "data_fetch")
    assert query.parent_id == data_fetch.span_id
    guardrail = next(span for span in decision_spans if span.name == "guardrail")
    assert guardrail.span_type == "GUARDRAIL" and guardrail.outputs == {"accepted": True, "reason": ""}
    check = next(span for span in decision_spans if span.name == "check")
    assert check.span_type == "GUARDRAIL" and check.outputs is not None and check.outputs["issues"] == []
    render = next(span for span in decision_spans if span.name == "render")
    assert render.span_type == "TOOL" and render.outputs is not None and "path" not in render.outputs

    stored = json.dumps([trace.to_json() for trace in traces])
    assert "bob-token" not in stored
    assert "api_key" not in stored
