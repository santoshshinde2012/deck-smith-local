import pytest

from decksmith.adapters.local.file_templates import FileTemplateRepository
from decksmith.application.sql import SqlCompiler, validate_params
from decksmith.domain.errors import AccessDenied, InvalidParameters, UnknownTemplate
from decksmith.domain.principal import Principal
from decksmith.ports.catalog import TableRef

WINDOW = {"start_month": "2026-07-01", "end_month": "2026-10-01"}


class StubCatalog:
    def resolve(self, logical_name: str, principal: Principal) -> TableRef:
        if principal.user_id == "carol":
            raise AccessDenied(logical_name)
        return TableRef(logical=logical_name, physical=f"lake.{logical_name}", lineage=f"main.{logical_name}")


@pytest.fixture
def repo() -> FileTemplateRepository:
    return FileTemplateRepository()


def test_templates_load(repo: FileTemplateRepository) -> None:
    ids = {t.id for t in repo.list()}
    assert ids == {
        "active_subscriptions",
        "churn_by_segment",
        "churn_rate_quarter",
        "churn_trend_monthly",
        "nrr_quarter",
    }
    assert repo.get("nrr_quarter").tables == ("cs.revenue_monthly",)
    with pytest.raises(UnknownTemplate):
        repo.get("drop_table")


def test_compile_transpiles_to_duckdb(repo: FileTemplateRepository) -> None:
    query = SqlCompiler(StubCatalog(), "duckdb").compile(
        repo.get("churn_trend_monthly"), WINDOW, Principal(user_id="bob")
    )
    assert "lake.cs.churn_monthly" in query.sql
    assert "try_divide" not in query.sql.lower() and "$start_month" in query.sql
    assert query.tables[0].lineage == "main.cs.churn_monthly"


def test_compile_databricks_is_passthrough(repo: FileTemplateRepository) -> None:
    query = SqlCompiler(StubCatalog(), "databricks").compile(
        repo.get("churn_rate_quarter"), WINDOW, Principal(user_id="bob")
    )
    assert "try_divide" in query.sql and ":start_month" in query.sql


def test_compile_propagates_access_denied(repo: FileTemplateRepository) -> None:
    with pytest.raises(AccessDenied):
        SqlCompiler(StubCatalog(), "duckdb").compile(repo.get("churn_rate_quarter"), WINDOW, Principal(user_id="carol"))


@pytest.mark.parametrize(
    "params",
    [
        {"start_month": "2026-07-01"},  # missing
        {**WINDOW, "region": "UK"},  # unknown
        {"start_month": "2026-07-15", "end_month": "2026-10-01"},  # pattern
        {"start_month": "2026-07-01'; DROP TABLE x; --", "end_month": "2026-10-01"},  # injection attempt
        {"start_month": "2026-13-01", "end_month": "2026-10-01"},  # invalid date
    ],
)
def test_params_validated(repo: FileTemplateRepository, params: dict[str, str]) -> None:
    with pytest.raises(InvalidParameters):
        validate_params(repo.get("churn_rate_quarter"), params)
