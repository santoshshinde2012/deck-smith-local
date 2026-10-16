"""Compile an approved Databricks SQL template for the active data source.

Templates are written once, in Databricks SQL. {{table:schema.name}} markers are resolved through the
Catalog port, parameters are validated against the template, and sqlglot transpiles to the source's
dialect (a no-op on Databricks, DuckDB locally).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import sqlglot

from decksmith.domain.errors import InvalidParameters
from decksmith.domain.principal import Principal
from decksmith.ports.catalog import Catalog, TableRef
from decksmith.ports.templates import SqlTemplate

_TABLE = re.compile(r"\{\{table:([a-z_]+\.[a-z_]+)\}\}")


@dataclass(frozen=True)
class CompiledQuery:
    sql: str
    params: dict[str, object]
    tables: tuple[TableRef, ...]


class SqlCompiler:
    def __init__(self, catalog: Catalog, target_dialect: str) -> None:
        self._catalog = catalog
        self._dialect = target_dialect

    def compile(self, template: SqlTemplate, params: dict[str, str], principal: Principal) -> CompiledQuery:
        values = validate_params(template, params)
        refs: dict[str, TableRef] = {}

        def _resolve(match: re.Match[str]) -> str:
            logical = match.group(1)
            if logical not in refs:
                refs[logical] = self._catalog.resolve(logical, principal)
            return refs[logical].physical

        databricks_sql = _TABLE.sub(_resolve, template.sql)
        sql = (
            databricks_sql
            if self._dialect == "databricks"
            else sqlglot.transpile(databricks_sql, read="databricks", write=self._dialect)[0]
        )
        return CompiledQuery(sql=sql, params=values, tables=tuple(refs.values()))


def validate_params(template: SqlTemplate, params: dict[str, str]) -> dict[str, object]:
    expected = {p.name: p for p in template.params}
    unknown = set(params) - set(expected)
    missing = set(expected) - set(params)
    if unknown or missing:
        raise InvalidParameters(f"{template.id}: unknown {sorted(unknown)}, missing {sorted(missing)}")
    values: dict[str, object] = {}
    for name, spec in expected.items():
        raw = params[name]
        if spec.allowed and raw not in spec.allowed:
            raise InvalidParameters(f"{template.id}.{name}: {raw!r} not in {spec.allowed}")
        if spec.pattern and not re.fullmatch(spec.pattern, raw):
            raise InvalidParameters(f"{template.id}.{name}: {raw!r} does not match {spec.pattern}")
        try:
            values[name] = date.fromisoformat(raw) if spec.type == "date" else int(raw) if spec.type == "int" else raw
        except ValueError as exc:
            raise InvalidParameters(f"{template.id}.{name}: {exc}") from exc
    return values
