"""Who a request runs as. Mirrors the OBO identity Databricks Apps forwards."""

from pydantic import BaseModel, ConfigDict, Field


class Principal(BaseModel):
    """An authenticated user or service principal."""

    model_config = ConfigDict(frozen=True)

    user_id: str = Field(min_length=1)
    display_name: str = ""
    groups: tuple[str, ...] = ()
    is_service_principal: bool = False
    token: str = Field(default="", repr=False, exclude=True)
