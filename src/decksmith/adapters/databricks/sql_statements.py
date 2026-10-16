"""DataSource over the Databricks SQL Statement Execution API, called with the user's own token (OBO)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import httpx

from decksmith.domain.errors import AccessDenied, DeckSmithError
from decksmith.domain.principal import Principal
from decksmith.ports.data_source import QueryResult


class DatabricksSqlDataSource:
    dialect = "databricks"

    def __init__(self, host: str, warehouse_id: str, client: httpx.Client | None = None) -> None:
        self._warehouse = warehouse_id
        self._client = client or httpx.Client(base_url=host.rstrip("/"), timeout=60)

    def execute(self, sql: str, params: dict[str, Any], principal: Principal) -> QueryResult:
        body = {
            "statement": sql,
            "warehouse_id": self._warehouse,
            "wait_timeout": "30s",
            "disposition": "INLINE",
            "format": "JSON_ARRAY",
            "parameters": [
                {
                    "name": k,
                    "value": v.isoformat() if isinstance(v, date) else str(v),
                    "type": "DATE" if isinstance(v, date) else "STRING",
                }
                for k, v in params.items()
            ],
        }
        response = self._client.post(
            "/api/2.0/sql/statements", json=body, headers={"Authorization": f"Bearer {principal.token}"}
        )
        if response.status_code == 403:
            raise AccessDenied(response.text)
        response.raise_for_status()
        payload = response.json()
        state = payload.get("status", {}).get("state")
        if state != "SUCCEEDED":
            raise DeckSmithError(f"statement {payload.get('statement_id')} ended {state}")
        columns = tuple(c["name"] for c in payload["manifest"]["schema"]["columns"])
        rows = tuple(tuple(_cast(v) for v in r) for r in payload.get("result", {}).get("data_array", []) or [])
        return QueryResult(
            columns=columns, rows=rows, statement_id=payload["statement_id"], executed_at=datetime.now(UTC)
        )


def _cast(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return value
    return value
