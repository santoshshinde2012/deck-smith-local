import json
import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from decksmith.config import Settings
from decksmith.domain.errors import ALL_ERRORS, DeckSmithError
from decksmith.observability import JsonFormatter, bind_run_id, get_logger, reset_run_id


@pytest.mark.parametrize(
    "overrides",
    [
        {"data_source": "databricks"},
        {"catalog": "unity_catalog"},
        {"identity": "jwt", "jwt_secret": "short"},
        {"llm": "portkey", "portkey_config_dir": Path("/nonexistent")},
        {
            "databricks_host": "http://insecure",
            "databricks_warehouse_id": "w",
            "data_source": "databricks",
            "catalog": "unity_catalog",
        },
    ],
)
def test_settings_reject_bad_combinations(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_settings_accept_databricks_combo() -> None:
    s = Settings(
        _env_file=None,
        data_source="databricks",
        catalog="unity_catalog",  # type: ignore[call-arg]
        databricks_host="https://dbc.example.com",
        databricks_warehouse_id="w",
    )
    assert s.catalog == "unity_catalog"


def test_error_taxonomy_is_complete() -> None:
    codes = [e.code for e in ALL_ERRORS]
    assert len(codes) == len(set(codes))
    assert all(issubclass(e, DeckSmithError) and 400 <= e.status_code < 600 for e in ALL_ERRORS)
    documented = (Path(__file__).resolve().parents[2] / "docs" / "errors.md").read_text()
    assert all(f"`{c}`" in documented for c in codes)


def test_json_logs_carry_run_id() -> None:
    record = logging.makeLogRecord(
        {"name": "decksmith.x", "msg": "run_started", "levelno": 20, "levelname": "INFO", "status": "done"}
    )
    token = bind_run_id("r-1")
    try:
        line = json.loads(JsonFormatter().format(record))
    finally:
        reset_run_id(token)
    assert line["event"] == "run_started" and line["run_id"] == "r-1" and line["status"] == "done"
    assert get_logger("x").name == "decksmith.x"
