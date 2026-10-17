"""DeckSpec: the JSON contract the Writer produces and the renderer consumes.

Mirrors the design's JSON Schema (draft 2020-12): closed objects, a fixed layout enum, length caps,
at most six bullets and four KPIs per slide, and digits only through {{fact:id}} placeholders.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Layout = Literal["title", "section", "kpi", "chart", "table", "bullets", "two_content", "appendix_sources"]

_STRICT = ConfigDict(extra="forbid")


class Kpi(BaseModel):
    model_config = _STRICT
    label: str = Field(min_length=1, max_length=60)
    fact_id: str = Field(pattern=r"^f[0-9]+$")
    delta_fact_id: str | None = Field(default=None, pattern=r"^f[0-9]+$")


class Series(BaseModel):
    model_config = _STRICT
    name: str = Field(min_length=1, max_length=60)
    fact_id: str = Field(pattern=r"^f[0-9]+$")


class Chart(BaseModel):
    model_config = _STRICT
    type: Literal["line", "bar", "column"]
    series: list[Series] = Field(min_length=1, max_length=4)


class Slide(BaseModel):
    model_config = _STRICT
    slide_id: str = Field(pattern=r"^s[0-9]{2}$")
    layout: Layout
    title: str = Field(min_length=1, max_length=90)
    subtitle: str = Field(default="", max_length=140)
    bullets: list[str] = Field(default_factory=list, max_length=6)
    kpis: list[Kpi] = Field(default_factory=list, max_length=4)
    chart: Chart | None = None
    notes: str = Field(default="", max_length=1200)
    sources: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _layout_fields(self) -> Slide:
        if self.layout == "kpi" and not self.kpis:
            raise ValueError(f"{self.slide_id}: kpi layout needs kpis")
        if self.layout == "chart" and self.chart is None:
            raise ValueError(f"{self.slide_id}: chart layout needs a chart")
        for bullet in self.bullets:
            if len(bullet) > 160:
                raise ValueError(f"{self.slide_id}: bullet longer than 160 characters")
        return self

    def texts(self) -> list[str]:
        """Every free-text field the numeric-integrity check must scan."""
        return [self.title, self.subtitle, *self.bullets, *(k.label for k in self.kpis)]

    def fact_refs(self) -> set[str]:
        refs = {k.fact_id for k in self.kpis} | {k.delta_fact_id for k in self.kpis if k.delta_fact_id}
        if self.chart:
            refs |= {s.fact_id for s in self.chart.series}
        return refs | set(self.sources)


class DeckSpec(BaseModel):
    model_config = _STRICT
    spec_version: Literal["1.0"] = "1.0"
    template_id: str = Field(pattern=r"^[a-z0-9_]+@[0-9]+\.[0-9]+$")
    title: str = Field(min_length=1, max_length=90)
    audience: Literal["exec", "team", "board"]
    period: str = Field(min_length=1, max_length=20)
    slides: list[Slide] = Field(min_length=1, max_length=25)

    @model_validator(mode="after")
    def _unique_ids(self) -> DeckSpec:
        ids = [s.slide_id for s in self.slides]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate slide_id")
        return self
