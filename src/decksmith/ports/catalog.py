"""Catalog port: resolves a logical table name to the physical object a principal may query."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from decksmith.domain.principal import Principal


class TableRef(BaseModel):
    """A resolved table: what to put in SQL, and what to record as lineage."""

    model_config = ConfigDict(frozen=True)

    logical: str  # e.g. "cs.churn_monthly"
    physical: str  # e.g. "lake.cs.v_churn_monthly__alice" locally, "main.cs.churn_monthly" on Databricks
    lineage: str  # the governed table name recorded in the fact's provenance


@runtime_checkable
class Catalog(Protocol):
    def resolve(self, logical_name: str, principal: Principal) -> TableRef:
        """Return the table to query for this principal, or raise AccessDenied."""
        ...
