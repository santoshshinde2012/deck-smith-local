"""Catalog for Databricks: governed names pass straight through; UC enforces row filters and masks."""

from __future__ import annotations

from decksmith.domain.principal import Principal
from decksmith.ports.catalog import TableRef


class UnityCatalogPassthrough:
    def __init__(self, catalog: str = "main") -> None:
        self._catalog = catalog

    def resolve(self, logical_name: str, principal: Principal) -> TableRef:
        name = f"{self._catalog}.{logical_name}"
        return TableRef(logical=logical_name, physical=name, lineage=name)
