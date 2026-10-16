"""Structured logging: one JSON object per line, with run_id correlation.

Standard library only, so every layer may use it. ``configure_logging`` is called once by the
composition root; library code only calls ``get_logger``. Never log tokens, prompts or row data:
log identifiers, counts, codes and durations.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

_run_id: ContextVar[str] = ContextVar("decksmith_run_id", default="")
_RESERVED = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}


def bind_run_id(run_id: str) -> object:
    """Attach run_id to every log line in this context; returns a token for ``reset_run_id``."""
    return _run_id.set(run_id)


def reset_run_id(token: object) -> None:
    _run_id.reset(token)  # type: ignore[arg-type]


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
        }
        if run_id := _run_id.get():
            payload["run_id"] = run_id
        payload.update({k: v for k, v in vars(record).items() if k not in _RESERVED and not k.startswith("_")})
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", json_format: bool = True) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter() if json_format else logging.Formatter("%(levelname)s %(name)s %(message)s"))
    root = logging.getLogger("decksmith")
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    root.propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name if name.startswith("decksmith") else f"decksmith.{name}")
