"""DataSource port: executes a parameterised SQL statement as a principal."""

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from decksmith.domain.principal import Principal


class QueryResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    statement_id: str
    executed_at: datetime


@runtime_checkable
class DataSource(Protocol):
    dialect: str
    """sqlglot dialect name the source executes (e.g. "duckdb", "databricks")."""

    def execute(self, sql: str, params: dict[str, Any], principal: Principal) -> QueryResult:
        """Run sql (already in this source's dialect) with named parameters."""
        ...
