"""TemplateRepository port: the approved, parameterised SQL templates. The LLM never writes SQL."""

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from decksmith.domain.facts import FactFormat, FactKind


class TemplateParam(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    type: Literal["date", "string", "int"]
    pattern: str = ""
    allowed: tuple[str, ...] = ()


class SqlTemplate(BaseModel):
    """A template written in Databricks SQL; {{table:cs.x}} markers are resolved by the Catalog."""

    model_config = ConfigDict(frozen=True)
    id: str
    description: str
    kind: FactKind
    format: FactFormat
    unit: str = ""
    params: tuple[TemplateParam, ...] = ()
    tables: tuple[str, ...] = Field(default=())
    sql: str


@runtime_checkable
class TemplateRepository(Protocol):
    def get(self, template_id: str) -> SqlTemplate: ...

    def list(self) -> list[SqlTemplate]: ...
