from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from decksmith.adapters.local.fake_llm import FakeLLM
from decksmith.adapters.local.pptx_renderer import PptxRenderer
from decksmith.adapters.local.state_stores import InMemoryStateStore
from decksmith.bootstrap import Container, build_container
from decksmith.config import Settings
from decksmith.domain.facts import Fact, FactRegistry, FactSource
from decksmith.domain.principal import Principal
from decksmith.seed.generate import build

REQUEST = "Build the Q3 2026 customer retention review for the exec team"


@pytest.fixture(scope="session")
def lakehouse(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("lake") / "lakehouse.duckdb")


@pytest.fixture
def settings(lakehouse: Path, tmp_path: Path) -> Settings:
    return Settings(_env_file=None, duckdb_path=lakehouse, output_dir=tmp_path / "out")  # type: ignore[call-arg]


@pytest.fixture
def make_container(settings: Settings) -> Callable[..., Container]:
    def _make(llm: FakeLLM | None = None, **overrides: object) -> Container:
        return build_container(settings, llm=llm or FakeLLM(), **overrides)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def container(make_container: Callable[..., Container]) -> Container:
    return make_container()


def user(name: str) -> Principal:
    return Principal(user_id=name, token=f"{name}-token")


@pytest.fixture
def bob() -> Principal:
    return user("bob")


@pytest.fixture
def alice() -> Principal:
    return user("alice")


@pytest.fixture
def carol() -> Principal:
    return user("carol")


def _source(template: str) -> FactSource:
    return FactSource(
        template_id=template,
        statement_id="fixture",
        tables=("main.cs.churn_monthly",),
        as_of=datetime(2026, 10, 1, tzinfo=UTC),
    )


@pytest.fixture
def facts() -> FactRegistry:
    return FactRegistry(
        [
            Fact(
                id="f1",
                kind="scalar",
                label="Churn rate",
                format="pct1",
                value=0.0236,
                source=_source("churn_rate_quarter"),
            ),
            Fact(
                id="f2",
                kind="scalar",
                label="Active subscriptions",
                format="int",
                value=6172,
                source=_source("active_subscriptions"),
            ),
            Fact(
                id="f3",
                kind="series",
                label="Monthly churn",
                format="pct1",
                categories=("2026-07", "2026-08", "2026-09"),
                values=(0.0245, 0.0240, 0.0224),
                source=_source("churn_trend_monthly"),
            ),
        ]
    )


@pytest.fixture
def spec_dict() -> dict[str, object]:
    return {
        "spec_version": "1.0",
        "template_id": "corp_default@1.0",
        "title": "Customer retention review",
        "audience": "exec",
        "period": "2026-Q3",
        "slides": [
            {"slide_id": "s01", "layout": "title", "title": "Customer retention review", "subtitle": "Exec"},
            {
                "slide_id": "s02",
                "layout": "kpi",
                "title": "Retention at a glance",
                "kpis": [{"label": "Churn rate", "fact_id": "f1"}, {"label": "Active", "fact_id": "f2"}],
                "bullets": ["Churn reached {{fact:f1}} this quarter"],
                "sources": ["f1", "f2"],
            },
            {
                "slide_id": "s03",
                "layout": "chart",
                "title": "Churn is easing",
                "chart": {"type": "line", "series": [{"name": "Monthly churn", "fact_id": "f3"}]},
                "sources": ["f3"],
            },
            {
                "slide_id": "s04",
                "layout": "bullets",
                "title": "What we do next",
                "bullets": ["Focus on SMB onboarding", "Review UK pricing"],
            },
            {"slide_id": "s05", "layout": "appendix_sources", "title": "Sources", "sources": ["f1", "f2", "f3"]},
        ],
    }


@pytest.fixture
def renderer(tmp_path: Path) -> PptxRenderer:
    return PptxRenderer(tmp_path / "decks")


@pytest.fixture
def memory_store() -> InMemoryStateStore:
    return InMemoryStateStore()
