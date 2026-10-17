"""Graph state. Plain JSON-able values only, so any checkpointer (memory, Postgres, Lakebase) can store it."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class DeckState(TypedDict, total=False):
    run_id: str
    user_id: str
    request_text: str
    intake: dict[str, Any]
    outline: dict[str, Any]
    approval: dict[str, Any]
    feedback: str
    facts: list[dict[str, Any]]
    spec: dict[str, Any]
    artifact: dict[str, Any]
    issues: list[str]
    writer_loops: int
    schema_valid_first_try: bool
    status: str
    error: str
    usage: Annotated[list[dict[str, Any]], operator.add]
