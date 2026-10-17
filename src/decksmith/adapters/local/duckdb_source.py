"""DataSource over a DuckDB file: the laptop stand-in for a Databricks SQL warehouse."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from decksmith.domain.principal import Principal
from decksmith.ports.data_source import QueryResult


class DuckDBDataSource:
    dialect = "duckdb"

    def __init__(self, database: Path, catalog_alias: str = "lake") -> None:
        if not database.exists():
            raise FileNotFoundError(f"{database} not found; run `make seed` first")
        self._database = database
        self._alias = catalog_alias

    def _connect(self) -> duckdb.DuckDBPyConnection:
        con = duckdb.connect()
        con.execute(f"ATTACH '{self._database}' AS {self._alias} (READ_ONLY)")
        return con

    def execute(self, sql: str, params: dict[str, Any], principal: Principal) -> QueryResult:
        with self._connect() as con:
            cursor = con.execute(sql, params)
            columns = tuple(d[0] for d in cursor.description or ())
            rows = tuple(tuple(r) for r in cursor.fetchall())
        return QueryResult(
            columns=columns, rows=rows, statement_id=f"duckdb-{uuid.uuid4().hex[:12]}", executed_at=datetime.now(UTC)
        )

    def view_exists(self, physical_name: str) -> bool:
        catalog, schema, name = physical_name.split(".")
        with self._connect() as con:
            found = con.execute(
                "SELECT 1 FROM information_schema.tables"
                " WHERE table_catalog = ? AND table_schema = ? AND table_name = ?",
                [catalog, schema, name],
            ).fetchone()
        return found is not None
