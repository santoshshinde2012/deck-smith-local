"""StateStore adapters: in-memory for tests, Postgres for the local stack (and Lakebase in production)."""

from __future__ import annotations

from contextlib import ExitStack
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver


class InMemoryStateStore:
    def __init__(self) -> None:
        self._saver = InMemorySaver()

    def checkpointer(self) -> Any:
        return self._saver

    def close(self) -> None:
        return None


class PostgresStateStore:
    """LangGraph PostgresSaver. Point the DSN at local Postgres, or at Lakebase on Databricks."""

    def __init__(self, dsn: str) -> None:
        from langgraph.checkpoint.postgres import PostgresSaver

        self._stack = ExitStack()
        self._saver = self._stack.enter_context(PostgresSaver.from_conn_string(dsn))
        self._saver.setup()

    def checkpointer(self) -> Any:
        return self._saver

    def close(self) -> None:
        self._stack.close()
