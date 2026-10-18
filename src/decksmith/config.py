"""Settings. Every adapter choice is configuration, not code (DECKSMITH_* environment variables)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root: the checkout in development, DECKSMITH_HOME (/app) inside the container image.
ROOT = Path(os.environ.get("DECKSMITH_HOME") or Path(__file__).resolve().parents[2])


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
    theme: Literal["meridian", "harbor", "graphite"] = "meridian"
    postgres_dsn: str = "postgresql://decksmith:decksmith@localhost:5433/decksmith"
    mlflow_tracking_uri: str = "http://localhost:5001"
    mlflow_experiment: str = "decksmith-local"
    portkey_base_url: str = "http://localhost:8787"
    portkey_api_key: str = "local"
    portkey_config_dir: Path = ROOT / "configs" / "portkey"
    llm_api_key: SecretStr = SecretStr("")  # your provider key for llm=portkey (never logged or stored)
    uc_oss_url: str = "http://localhost:8081"
    jwt_secret: str = ""
    env: str = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = True
    max_request_chars: int = Field(default=2000, ge=10, le=20000)

    # Databricks (tier L3).
    databricks_host: str = ""
    databricks_warehouse_id: str = ""
    databricks_catalog: str = "main"

    @model_validator(mode="after")
    def _check_combination(self) -> Settings:
        """Fail fast at start-up on an adapter combination that cannot work."""
        problems: list[str] = []
        if self.llm == "portkey" and not self.portkey_config_dir.is_dir():
            problems.append(f"llm=portkey needs portkey_config_dir ({self.portkey_config_dir}) to exist")
        if self.data_source == "databricks" and not (self.databricks_host and self.databricks_warehouse_id):
            problems.append("data_source=databricks needs databricks_host and databricks_warehouse_id")
        if self.catalog == "unity_catalog" and self.data_source != "databricks":
            problems.append("catalog=unity_catalog needs data_source=databricks")
        if self.catalog in ("per_user_views", "uc_oss") and self.data_source != "duckdb":
            problems.append(f"catalog={self.catalog} needs data_source=duckdb")
        if self.identity == "jwt" and len(self.jwt_secret) < 32:
            problems.append("identity=jwt needs DECKSMITH_JWT_SECRET of at least 32 characters")
        if self.databricks_host and not self.databricks_host.startswith("https://"):
            problems.append("databricks_host must start with https://")
        if problems:
            raise ValueError("; ".join(problems))
        return self
