"""StateStore adapters: in-memory for tests, Postgres for the local stack (and Lakebase in production)."""

from __future__ import annotations

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
    """LangGraph PostgresSaver over a connection pool. Point the DSN at local Postgres, or at Lakebase.

    A pool (not one shared connection) because callers such as ``mlflow.genai.evaluate`` run the
    graph from several threads; the pool also replaces connections the server has closed.
    """

    def __init__(self, dsn: str, *, max_size: int = 8) -> None:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        self._pool: ConnectionPool[Any] = ConnectionPool(
            dsn,
            min_size=1,
            max_size=max_size,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
            check=ConnectionPool.check_connection,
            open=True,
        )
        self._saver = PostgresSaver(self._pool)
        self._saver.setup()

    def checkpointer(self) -> Any:
        return self._saver

    def close(self) -> None:
        self._pool.close()
