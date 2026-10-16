"""SQL templates stored as .sql files with a small comment header."""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path

from decksmith.domain.errors import UnknownTemplate
from decksmith.ports.templates import SqlTemplate, TemplateParam


class FileTemplateRepository:
    """Header lines: `-- id:`, `-- description:`, `-- kind:`, `-- format:`, `-- unit:`,
    and `-- param: name type [pattern]`."""

    def __init__(self, directory: Path | None = None) -> None:
        root = directory or Path(str(resources.files("decksmith") / "sql" / "templates"))
        self._templates = {t.id: t for t in (_parse(p.read_text()) for p in sorted(root.glob("*.sql")))}

    def get(self, template_id: str) -> SqlTemplate:
        try:
            return self._templates[template_id]
        except KeyError as exc:
            raise UnknownTemplate(template_id) from exc

    def list(self) -> list[SqlTemplate]:
        return list(self._templates.values())


def _parse(text: str) -> SqlTemplate:
    meta: dict[str, str] = {}
    params: list[TemplateParam] = []
    body: list[str] = []
    for line in text.splitlines():
        if line.startswith("-- ") and ":" in line and not body:
            key, _, value = line[3:].partition(":")
            if key.strip() == "param":
                parts = value.split()
                params.append(TemplateParam(name=parts[0], type=parts[1], pattern=parts[2] if len(parts) > 2 else ""))  # type: ignore[arg-type]
            else:
                meta[key.strip()] = value.strip()
        else:
            body.append(line)
    sql = "\n".join(body).strip()
    tables = tuple(sorted(set(re.findall(r"\{\{table:([a-z_]+\.[a-z_]+)\}\}", sql))))
    return SqlTemplate(
        id=meta["id"],
        description=meta.get("description", ""),
        kind=meta["kind"],  # type: ignore[arg-type]
        format=meta["format"],  # type: ignore[arg-type]
        unit=meta.get("unit", ""),
        params=tuple(params),
        tables=tables,
        sql=sql,
    )
