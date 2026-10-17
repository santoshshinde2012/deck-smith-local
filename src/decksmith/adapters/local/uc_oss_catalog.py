"""Decorator Catalog that checks a table is registered in Unity Catalog OSS before delegating.

Keeps catalog names honest locally (main.cs.churn_monthly must exist in UC OSS, as in production),
while row filtering stays with the inner catalog, because UC OSS does not enforce row filters.
"""

from __future__ import annotations

import httpx

from decksmith.domain.errors import AccessDenied
from decksmith.domain.principal import Principal
from decksmith.ports.catalog import Catalog, TableRef


class UnityCatalogOssCatalog:
    def __init__(
        self, inner: Catalog, base_url: str, catalog: str = "main", client: httpx.Client | None = None
    ) -> None:
        self._inner = inner
        self._catalog = catalog
        self._client = client or httpx.Client(base_url=base_url.rstrip("/"), timeout=10)
        self._known: set[str] = set()

    def resolve(self, logical_name: str, principal: Principal) -> TableRef:
        full = f"{self._catalog}.{logical_name}"
        if full not in self._known:
            response = self._client.get(f"/api/2.1/unity-catalog/tables/{full}")
            if response.status_code == 404:
                raise AccessDenied(f"{full} is not registered in Unity Catalog")
            response.raise_for_status()
            self._known.add(full)
        return self._inner.resolve(logical_name, principal)
