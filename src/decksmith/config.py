"""Settings. Every adapter choice is configuration, not code (DECKSMITH_* environment variables)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DECKSMITH_", env_file=".env", extra="ignore")

    # Adapter selection, one per port.
    llm: Literal["fake", "portkey"] = "fake"
    data_source: Literal["duckdb", "databricks"] = "duckdb"
    catalog: Literal["per_user_views", "uc_oss", "unity_catalog"] = "per_user_views"
    state_store: Literal["memory", "postgres"] = "memory"
    tracer: Literal["noop", "mlflow"] = "noop"
    identity: Literal["static", "jwt", "databricks_apps"] = "static"

    # Local stack.
    duckdb_path: Path = ROOT / "data" / "lakehouse.duckdb"
    output_dir: Path = ROOT / "out"
    pptx_template: Path | None = None
    postgres_dsn: str = "postgresql://decksmith:decksmith@localhost:5433/decksmith"
    mlflow_tracking_uri: str = "http://localhost:5001"
    mlflow_experiment: str = "decksmith-local"
    portkey_base_url: str = "http://localhost:8787"
    portkey_api_key: str = "local"
    portkey_config_dir: Path = ROOT / "configs" / "portkey"
    uc_oss_url: str = "http://localhost:8081"
    jwt_secret: str = ""
    env: str = "local"

    # Databricks (tier L3).
    databricks_host: str = ""
    databricks_warehouse_id: str = ""
    databricks_catalog: str = "main"
