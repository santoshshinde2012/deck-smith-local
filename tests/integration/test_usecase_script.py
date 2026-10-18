from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi.testclient import TestClient
from pptx.chart.data import CategoryChartData
from scripts.e2e_usecase import UseCase

from decksmith.bootstrap import Container
from decksmith.interfaces.api import create_app


@pytest.fixture
def usecase(container: Container, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> UseCase:
    client = TestClient(create_app(container))

    def call(self: UseCase, user: str | None, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {"Authorization": f"Bearer {user}-token"} if user else {}
        return cast(httpx.Response, client.request(method, path, headers=headers, **kwargs))

    monkeypatch.setattr(UseCase, "call", call)
    return UseCase("http://testserver", tmp_path)


def _edited_deck(usecase: UseCase) -> None:
    usecase.request_outline("bob")
    usecase.edit_outline()
    usecase.approve("bob")
    usecase.download("bob")


def test_usecase_finishes_the_edited_run_and_checks_chart_values(usecase: UseCase) -> None:
    usecase.request_outline("bob")
    original_run = usecase.ctx["bob_run"]
    usecase.edit_outline()
    usecase.approve("bob")
    usecase.download("bob")
    assert usecase.ctx["bob_run"] == original_run
    assert usecase.ctx["bob_view"]["artifact"]["slide_count"] == 4
    assert "3 chart points match facts" in usecase.numbers_trace_to_facts("bob")


def test_usecase_detects_a_tampered_native_chart(usecase: UseCase) -> None:
    _edited_deck(usecase)
    chart = next(shape.chart for slide in usecase.ctx["bob_deck"].slides for shape in slide.shapes if shape.has_chart)
    data = CategoryChartData()  # type: ignore[no-untyped-call]
    data.categories = [category.label for category in chart.plots[0].categories]
    values = list(chart.series[0].values)
    values[0] = 0.9
    data.add_series(chart.series[0].name, values)  # type: ignore[no-untyped-call]
    chart.replace_data(data)
    with pytest.raises(AssertionError, match="chart values differ"):
        usecase.numbers_trace_to_facts("bob")
