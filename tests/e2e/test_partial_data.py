from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from decksmith.adapters.local.duckdb_source import DuckDBDataSource
from decksmith.adapters.local.policy_catalog import PerUserViewCatalog
from decksmith.bootstrap import Container
from decksmith.domain.errors import AccessDenied
from decksmith.domain.principal import Principal
from decksmith.ports.data_source import QueryResult
from tests.conftest import REQUEST

pytestmark = pytest.mark.e2e


class PartialDataSource:
    dialect = "duckdb"

    def __init__(self, inner: DuckDBDataSource, denied: bool) -> None:
        self._inner = inner
        self._denied = denied

    def execute(self, sql: str, params: dict[str, Any], principal: Principal) -> QueryResult:
        if "GROUP BY SEGMENT" in sql.upper():
            if self._denied:
                raise AccessDenied("The requested table is not visible")
            return QueryResult(
                columns=("segment", "churn_rate"),
                rows=(),
                statement_id="empty-segment-result",
                executed_at=datetime.now(UTC),
            )
        return self._inner.execute(sql, params, principal)


@pytest.mark.parametrize("denied", [True, False], ids=["denied", "empty-result"])
def test_partial_data_refuses_before_writer_without_changing_the_approved_outline(
    denied: bool, make_container: Callable[..., Container], lakehouse: Path, bob: Principal
) -> None:
    inner = DuckDBDataSource(lakehouse)
    container = make_container(source=PartialDataSource(inner, denied), catalog=PerUserViewCatalog(inner.view_exists))
    try:
        first = container.service.start(REQUEST, bob)
        assert first.status == "awaiting_approval"
        refused = container.service.decide(first.run_id, "approve", bob)
        cause = "Some requested data is not visible to you" if denied else "Some requested queries returned no data"
        assert refused.status == "no_data" and refused.error.startswith(cause)
        assert "approve a new outline" in refused.error
        assert refused.outline == first.outline
        assert refused.facts == [] and refused.artifact is None and refused.spec is None
        assert all(usage["node"] != "writer" for usage in refused.usage)
        assert not list(container.settings.output_dir.glob("*.pptx"))
    finally:
        container.close()


def test_period_without_data_is_not_reported_as_a_permission_denial(
    container: Container, bob: Principal, carol: Principal
) -> None:
    """The seed data ends in September 2026, so Q4 returns no rows even for a user who sees every region."""
    for principal, expected in (
        (bob, "None of the requested queries returned data for you"),
        (carol, "None of the requested data is visible to you"),
    ):
        first = container.service.start("Build the Q4 2026 customer retention review for the exec team", principal)
        refused = container.service.decide(first.run_id, "approve", principal)
        assert refused.status == "no_data" and refused.error.startswith(expected), refused.error
        assert refused.facts == [] and refused.artifact is None
