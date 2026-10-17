"""Facts: typed, provenanced numbers. The only way a number reaches a slide."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FactKind = Literal["scalar", "series"]
FactFormat = Literal["pct1", "int", "currency0", "decimal2"]


class FactSource(BaseModel):
    """Where a fact came from: the query and the tables behind it."""

    model_config = ConfigDict(frozen=True)

    type: Literal["sql", "genie", "uc_function"] = "sql"
    template_id: str
    statement_id: str
    tables: tuple[str, ...]
    as_of: datetime


class Fact(BaseModel):
    """A single scalar or a categorical series, with provenance."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(pattern=r"^f[0-9]+$")
    kind: FactKind
    label: str = Field(min_length=1, max_length=120)
    unit: str = ""
    format: FactFormat = "decimal2"
    value: float | None = None
    categories: tuple[str, ...] = ()
    values: tuple[float, ...] = ()
    source: FactSource

    @model_validator(mode="after")
    def _shape(self) -> Fact:
        if self.kind == "scalar" and self.value is None:
            raise ValueError("scalar fact needs a value")
        if self.kind == "series" and len(self.categories) != len(self.values):
            raise ValueError("series fact needs one value per category")
        return self


class FactRegistry:
    """Append-only store of facts for one run. Only the DataFetch step adds to it."""

    def __init__(self, facts: list[Fact] | None = None) -> None:
        self._facts: dict[str, Fact] = {}
        for fact in facts or []:
            self._facts[fact.id] = fact

    def next_id(self) -> str:
        return f"f{len(self._facts) + 1}"

    def add(self, fact: Fact) -> Fact:
        if fact.id in self._facts:
            raise ValueError(f"duplicate fact id {fact.id}")
        self._facts[fact.id] = fact
        return fact

    def get(self, fact_id: str) -> Fact:
        return self._facts[fact_id]

    def __contains__(self, fact_id: object) -> bool:
        return fact_id in self._facts

    def __len__(self) -> int:
        return len(self._facts)

    def all(self) -> list[Fact]:
        return list(self._facts.values())

    def dump(self) -> list[dict[str, object]]:
        return [f.model_dump(mode="json") for f in self._facts.values()]

    @classmethod
    def load(cls, raw: list[dict[str, object]]) -> FactRegistry:
        return cls([Fact.model_validate(r) for r in raw])


def format_value(value: float, fmt: FactFormat, unit: str = "") -> str:
    """Render a number for a slide. The renderer, never the LLM, formats numbers."""
    if fmt == "pct1":
        return f"{value * 100:.1f}%"
    if fmt == "int":
        return f"{value:,.0f}"
    if fmt == "currency0":
        symbol = {"EUR": "€", "USD": "$", "GBP": "£"}.get(unit, "")
        return f"{symbol}{value:,.0f}"
    return f"{value:,.2f}"
