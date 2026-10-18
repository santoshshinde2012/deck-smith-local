import json
from collections.abc import Callable
from typing import Any

import pytest

from decksmith.adapters.local.duckdb_source import DuckDBDataSource
from decksmith.adapters.local.fake_llm import FakeLLM
from decksmith.bootstrap import Container
from decksmith.config import Settings
from decksmith.domain.errors import InvalidParameters
from decksmith.domain.principal import Principal
from decksmith.ports.data_source import QueryResult
from decksmith.ports.llm import LLMRequest, LLMResponse
from tests.conftest import REQUEST

pytestmark = pytest.mark.e2e


class ChangedWriter(FakeLLM):
    def __init__(self, change: str, *, once: bool = False) -> None:
        super().__init__()
        self.change = change
        self.once = once

    def complete(self, request: LLMRequest) -> LLMResponse:
        response = super().complete(request)
        if request.node != "writer" or (self.once and self.calls["writer"] > 1):
            return response
        spec = json.loads(response.text)
        if self.change == "series_in_text":
            spec["slides"][1]["bullets"] = ["Quarter churn {{fact:f4}}"]
        elif self.change == "invented_legend":
            spec["slides"][2]["chart"]["series"][0]["name"] = "Actual 99%"
        elif self.change == "invented_notes":
            spec["slides"][1]["notes"] = "Churn was 99%"
        elif self.change == "mixed_categories":
            spec["slides"][2]["chart"]["series"].append({"name": "Segments", "fact_id": "f5"})
        elif self.change == "missing_sources":
            spec["slides"][-1]["sources"] = []
        elif self.change == "dropped_slide":
            spec["slides"].pop(0)
        elif self.change == "changed_layout":
            spec["slides"][0]["layout"] = "section"
        elif self.change == "changed_audience":
            spec["audience"] = "board"
        elif self.change == "changed_period":
            spec["period"] = "2026-Q4"
        elif self.change == "changed_template":
            spec["template_id"] = "other@1.0"
        else:
            spec["slides"][0]["title"] = "A clearer retention headline"
        return response.model_copy(update={"text": json.dumps(spec)})


@pytest.mark.parametrize(
    "change",
    [
        "series_in_text",
        "invented_legend",
        "invented_notes",
        "mixed_categories",
        "missing_sources",
        "dropped_slide",
        "changed_layout",
        "changed_audience",
        "changed_period",
        "changed_template",
    ],
)
def test_invalid_writer_output_never_reaches_a_deck(
    make_container: Callable[..., Container], bob: Principal, change: str
) -> None:
    llm = ChangedWriter(change)
    service = make_container(llm=llm).service
    run = service.start(REQUEST, bob)
    result = service.decide(run.run_id, "approve", bob)
    assert result.status == "failed" and result.artifact is None
    assert result.issues and llm.calls["writer"] == 3


def test_writer_can_repair_integrity_and_improve_approved_titles(
    make_container: Callable[..., Container], bob: Principal
) -> None:
    llm = ChangedWriter("mixed_categories", once=True)
    service = make_container(llm=llm).service
    run = service.start(REQUEST, bob)
    result = service.decide(run.run_id, "approve", bob)
    assert result.status == "done" and result.issues == [] and llm.calls["writer"] == 2
    service = make_container(llm=ChangedWriter("improved_title")).service
    run = service.start(REQUEST, bob)
    result = service.decide(run.run_id, "approve", bob)
    assert result.status == "done" and result.spec is not None
    assert result.spec["slides"][0]["title"] == "A clearer retention headline"


class BadPlanner(FakeLLM):
    def complete(self, request: LLMRequest) -> LLMResponse:
        response = super().complete(request)
        if request.node == "planner":
            outline = json.loads(response.text)
            # A valid first request must not run before this later invalid request is rejected.
            outline["slides"][3]["data_requests"][0]["params"]["start_month"] = "2026-99-01"
            response = response.model_copy(update={"text": json.dumps(outline)})
        return response


class RecordingSource(DuckDBDataSource):
    queries: list[str]

    def execute(self, sql: str, params: dict[str, Any], principal: Principal) -> QueryResult:
        self.queries.append(sql)
        return super().execute(sql, params, principal)


def test_entire_plan_parameters_are_validated_before_queries(
    make_container: Callable[..., Container], settings: Settings, bob: Principal
) -> None:
    source = RecordingSource(settings.duckdb_path)
    source.queries = []
    service = make_container(llm=BadPlanner(), source=source).service
    with pytest.raises(InvalidParameters):
        service.start(REQUEST, bob)
    assert source.queries == []
