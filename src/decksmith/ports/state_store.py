"""StateStore port: durable agent state (LangGraph checkpoints in Lakebase on Databricks)."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StateStore(Protocol):
    def checkpointer(self) -> Any:
        """Return a LangGraph checkpoint saver. Typed Any so the port does not depend on LangGraph."""
        ...

    def close(self) -> None: ...
