"""Catalog that emulates UC row filters with per-user views (v_<table>__<user>).

Locally there is no Unity Catalog enforcement, so `make seed` creates one filtered view per test user
and per table. A user without a view is denied, which mirrors UC returning no access.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from decksmith.domain.errors import AccessDenied
from decksmith.domain.principal import Principal
from decksmith.ports.catalog import TableRef

_SAFE = re.compile(r"[^a-z0-9_]")


class PerUserViewCatalog:
    def __init__(
        self, exists: Callable[[str], bool], local_catalog: str = "lake", governed_catalog: str = "main"
    ) -> None:
        self._exists = exists
        self._local = local_catalog
        self._governed = governed_catalog

    def resolve(self, logical_name: str, principal: Principal) -> TableRef:
        schema, table = logical_name.split(".")
        user = _SAFE.sub("_", principal.user_id.lower())
        physical = f"{self._local}.{schema}.v_{table}__{user}"
        if not self._exists(physical):
            raise AccessDenied(f"{principal.user_id} has no access to {logical_name}")
        return TableRef(logical=logical_name, physical=physical, lineage=f"{self._governed}.{logical_name}")
