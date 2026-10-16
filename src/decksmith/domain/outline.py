"""The outline the Planner proposes and the user approves. It never contains numbers."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from decksmith.domain.deckspec import Layout


class DataRequest(BaseModel):
    """One question for the data layer: a named template plus validated parameters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    template_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    params: dict[str, str] = Field(default_factory=dict)
    label: str = Field(min_length=1, max_length=120)


class OutlineSlide(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slide_id: str = Field(pattern=r"^s[0-9]{2}$")
    layout: Layout
    title_hint: str = Field(min_length=1, max_length=120)
    data_requests: list[DataRequest] = Field(default_factory=list, max_length=4)


class Outline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deck_title: str = Field(min_length=1, max_length=120)
    audience: Literal["exec", "team", "board"] = "exec"
    period: str = Field(min_length=1, max_length=20)
    slides: list[OutlineSlide] = Field(min_length=1, max_length=15)


class Intake(BaseModel):
    """What the Intake step extracts from the request."""

    model_config = ConfigDict(extra="forbid")

    deck_type: Literal["kpi_review", "retention_review", "adhoc"] = "adhoc"
    audience: Literal["exec", "team", "board"] = "exec"
    period: str = Field(min_length=1, max_length=20)
    template_id: str = "corp_default@1.0"
