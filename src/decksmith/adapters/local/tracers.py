"""Tracer adapters: no-op, and MLflow 3 tracing (OSS server locally, Databricks-managed in production)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from typing import Any


class NoopTracer:
    def span(self, name: str, attributes: dict[str, Any] | None = None) -> Any:
        return nullcontext()


class MlflowTracer:
    def __init__(self, tracking_uri: str, experiment: str) -> None:
        import mlflow

        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment)
        self._mlflow = mlflow

    @contextmanager
    def span(self, name: str, attributes: dict[str, Any] | None = None) -> Iterator[Any]:
        with self._mlflow.start_span(name=name) as span:
            if attributes:
                span.set_attributes({k: str(v) for k, v in attributes.items()})
            yield span
