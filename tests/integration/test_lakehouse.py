from pathlib import Path

import duckdb
import pytest

from decksmith.adapters.local.duckdb_source import DuckDBDataSource
from decksmith.domain.principal import Principal
from decksmith.seed.generate import N_SUBSCRIPTIONS, REGIONS, build

pytestmark = pytest.mark.integration


def test_seed_is_deterministic(tmp_path: Path, lakehouse: Path) -> None:
    other = build(tmp_path / "again.duckdb")
    query = (
        "SELECT SUM(churned), SUM(active_start), ROUND(SUM(mrr_start)) "
        "FROM cs.churn_monthly JOIN cs.revenue_monthly USING (month, region, segment)"
    )
    with duckdb.connect(str(lakehouse), read_only=True) as a, duckdb.connect(str(other), read_only=True) as b:
        assert a.execute(query).fetchall() == b.execute(query).fetchall()


def test_seed_shape(lakehouse: Path) -> None:
    with duckdb.connect(str(lakehouse), read_only=True) as con:
        assert con.execute("SELECT COUNT(*) FROM cs.subscriptions").fetchone() == (N_SUBSCRIPTIONS,)
        assert con.execute("SELECT COUNT(DISTINCT month) FROM cs.churn_monthly").fetchone() == (12,)
        assert {r[0] for r in con.execute("SELECT DISTINCT region FROM cs.v_churn_monthly__bob").fetchall()} == set(
            REGIONS
        )
        assert {r[0] for r in con.execute("SELECT DISTINCT region FROM cs.v_churn_monthly__alice").fetchall()} == {
            "EU-West"
        }


def test_views_per_user(lakehouse: Path) -> None:
    source = DuckDBDataSource(lakehouse)
    assert source.view_exists("lake.cs.v_revenue_monthly__alice")
    assert not source.view_exists("lake.cs.v_revenue_monthly__carol")
    result = source.execute(
        "SELECT COUNT(*) FROM lake.cs.v_subscriptions__alice WHERE region <> $r",
        {"r": "EU-West"},
        Principal(user_id="alice"),
    )
    assert result.rows == ((0,),)


def test_source_is_read_only(lakehouse: Path) -> None:
    with pytest.raises(duckdb.Error):
        DuckDBDataSource(lakehouse).execute("DELETE FROM lake.cs.subscriptions", {}, Principal(user_id="bob"))
