"""DataSource over the Databricks SQL Statement Execution API, called with the user's own token (OBO)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from time import sleep
from typing import Any
from urllib.parse import quote

import httpx

from decksmith.domain.errors import AccessDenied, UpstreamError
from decksmith.domain.principal import Principal
from decksmith.ports.data_source import QueryResult


class DatabricksSqlDataSource:
    dialect = "databricks"

    def __init__(
        self,
        host: str,
        warehouse_id: str,
        client: httpx.Client | None = None,
        *,
        poll_interval: float = 1.0,
        max_poll_attempts: int = 120,
    ) -> None:
        if poll_interval < 0 or max_poll_attempts < 1:
            raise ValueError("poll_interval must be nonnegative and max_poll_attempts must be positive")
        self._warehouse = warehouse_id
        self._client = client or httpx.Client(base_url=host.rstrip("/"), timeout=60)
        self._poll_interval = poll_interval
        self._max_poll_attempts = max_poll_attempts

    def execute(self, sql: str, params: dict[str, Any], principal: Principal) -> QueryResult:
        body = {
            "statement": sql,
            "warehouse_id": self._warehouse,
            "wait_timeout": "30s",
            "on_wait_timeout": "CONTINUE",
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
        headers = {"Authorization": f"Bearer {principal.token}"}
        payload = self._request("POST", "/api/2.0/sql/statements", headers, body)
        statement_id = payload.get("statement_id")
        if not isinstance(statement_id, str) or not statement_id:
            raise UpstreamError("SQL warehouse returned no statement ID")
        statement_path = f"/api/2.0/sql/statements/{quote(statement_id, safe='')}"
        for _ in range(self._max_poll_attempts):
            if payload.get("status", {}).get("state") not in ("PENDING", "RUNNING"):
                break
            sleep(self._poll_interval)
            payload = self._request("GET", statement_path, headers)
        else:
            if payload.get("status", {}).get("state") in ("PENDING", "RUNNING"):
                raise UpstreamError("SQL statement did not finish within the polling limit")

        state = payload.get("status", {}).get("state")
        if state != "SUCCEEDED":
            status = payload.get("status", {})
            error = status.get("error", {})
            permission_codes = {"PERMISSION_DENIED", "INSUFFICIENT_PERMISSIONS", "INSUFFICIENT_PRIVILEGES"}
            if (
                error.get("error_code") in permission_codes
                or status.get("sql_state") == "42501"
                or error.get("sql_state") == "42501"
                or any(f"[{code}]" in error.get("message", "") for code in permission_codes)
            ):
                raise AccessDenied("The SQL warehouse denied access to the requested data")
            raise UpstreamError(f"SQL statement ended in state {state}")
        manifest = payload.get("manifest", {})
        if manifest.get("truncated"):
            raise UpstreamError("SQL warehouse truncated the result; no partial facts were accepted")
        if manifest.get("format", "JSON_ARRAY") != "JSON_ARRAY":
            raise UpstreamError("SQL warehouse returned an unsupported result format")
        try:
            columns = tuple(c["name"] for c in manifest["schema"]["columns"])
        except (KeyError, TypeError) as exc:
            raise UpstreamError("SQL warehouse returned no result schema") from exc
        rows = self._rows(payload, columns, statement_path, headers)
        return QueryResult(columns=columns, rows=rows, statement_id=statement_id, executed_at=datetime.now(UTC))

    def _request(
        self, method: str, path: str, headers: dict[str, str], body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            response = self._client.request(method, path, headers=headers, json=body)
            if response.status_code == 403:
                raise AccessDenied("The SQL warehouse denied access to the requested data")
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise UpstreamError("SQL warehouse request failed") from exc
        if not isinstance(payload, dict):
            raise UpstreamError("SQL warehouse returned an invalid response")
        return payload

    def _rows(
        self, payload: dict[str, Any], columns: tuple[str, ...], path: str, headers: dict[str, str]
    ) -> tuple[tuple[Any, ...], ...]:
        """Fetch every inline chunk and reject incomplete or inconsistent result sets."""
        manifest = payload["manifest"]
        total_chunks, total_rows = manifest.get("total_chunk_count"), manifest.get("total_row_count")
        result = payload.get("result")
        if result is None:
            if total_rows == 0:
                return ()
            raise UpstreamError("SQL warehouse returned no result data")
        rows: list[tuple[Any, ...]] = []
        chunk_index = 0
        while True:
            chunk = result.get("data_array") or []
            if (
                result.get("chunk_index", chunk_index) != chunk_index
                or result.get("row_offset", len(rows)) != len(rows)
                or result.get("row_count", len(chunk)) != len(chunk)
                or any(len(row) != len(columns) for row in chunk)
                or result.get("external_links")
            ):
                raise UpstreamError("SQL warehouse returned an inconsistent result chunk")
            rows.extend(
                tuple(_cast(value, manifest["schema"]["columns"][index]) for index, value in enumerate(row))
                for row in chunk
            )
            next_index = result.get("next_chunk_index")
            if next_index is not None and next_index != chunk_index + 1:
                raise UpstreamError("SQL warehouse skipped or repeated a result chunk")
            if (
                next_index is None
                and not result.get("next_chunk_internal_link")
                and (total_chunks is None or chunk_index + 1 >= total_chunks)
            ):
                break
            if total_chunks is not None and chunk_index + 1 >= total_chunks:
                raise UpstreamError("SQL warehouse returned more chunks than its result manifest")
            chunk_index += 1
            result = self._request("GET", f"{path}/result/chunks/{chunk_index}", headers)
        empty_result = not rows and total_chunks == 0 and chunk_index == 0
        if (total_chunks is not None and total_chunks != chunk_index + 1 and not empty_result) or (
            total_rows is not None and total_rows != len(rows)
        ):
            raise UpstreamError("SQL warehouse returned an incomplete result set")
        return tuple(rows)


def _cast(value: Any, column: dict[str, Any]) -> Any:
    type_name = str(column.get("type_name") or column.get("type_text") or "").split("(", 1)[0].upper()
    numeric_types = {
        "BYTE",
        "SHORT",
        "INT",
        "INTEGER",
        "LONG",
        "TINYINT",
        "SMALLINT",
        "BIGINT",
        "FLOAT",
        "DOUBLE",
        "REAL",
        "DECIMAL",
        "NUMERIC",
    }
    # A STRING category such as "001" is an identifier, not a numeric measurement.
    # Older offline fixtures omit the optional type metadata, so retain their numeric conversion.
    if type_name and type_name not in numeric_types:
        return value
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return value
    return value
