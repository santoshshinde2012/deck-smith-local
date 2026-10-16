"""Turn approved data requests into Facts. The only code path that creates a Fact."""

from __future__ import annotations

from decksmith.application.sql import SqlCompiler
from decksmith.domain.errors import AccessDenied
from decksmith.domain.facts import Fact, FactRegistry, FactSource
from decksmith.domain.outline import DataRequest
from decksmith.domain.principal import Principal
from decksmith.ports.data_source import DataSource, QueryResult
from decksmith.ports.templates import SqlTemplate, TemplateRepository


class FactFetcher:
    def __init__(self, templates: TemplateRepository, compiler: SqlCompiler, source: DataSource) -> None:
        self._templates = templates
        self._compiler = compiler
        self._source = source

    def fetch(self, request: DataRequest, principal: Principal, registry: FactRegistry) -> Fact | None:
        """Run one request; returns None when the principal's data has no rows (not an error)."""
        template = self._templates.get(request.template_id)
        try:
            query = self._compiler.compile(template, request.params, principal)
        except AccessDenied:
            return None
        result = self._source.execute(query.sql, query.params, principal)
        source = FactSource(
            template_id=template.id,
            statement_id=result.statement_id,
            tables=tuple(t.lineage for t in query.tables),
            as_of=result.executed_at,
        )
        fact = _to_fact(registry.next_id(), request.label, template, result, source)
        return registry.add(fact) if fact else None


def _to_fact(fact_id: str, label: str, template: SqlTemplate, result: QueryResult, source: FactSource) -> Fact | None:
    if template.kind == "scalar":
        if not result.rows or result.rows[0][0] is None:
            return None
        return Fact(
            id=fact_id,
            kind="scalar",
            label=label,
            unit=template.unit,
            format=template.format,
            value=float(result.rows[0][0]),
            source=source,
        )
    rows = [r for r in result.rows if r[1] is not None]
    if not rows:
        return None
    return Fact(
        id=fact_id,
        kind="series",
        label=label,
        unit=template.unit,
        format=template.format,
        categories=tuple(str(r[0]) for r in rows),
        values=tuple(float(r[1]) for r in rows),
        source=source,
    )
