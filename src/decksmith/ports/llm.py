"""LLMGateway port: every model call goes through one gateway (Portkey in the design)."""

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

Tier = Literal["small", "strong"]


class Message(BaseModel):
    model_config = ConfigDict(frozen=True)
    role: Literal["system", "user", "assistant"]
    content: str


class LLMRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    node: str
    tier: Tier
    messages: tuple[Message, ...]
    run_id: str
    user_hash: str = ""
    json_mode: bool = True
    temperature: float = Field(default=0.2, ge=0, le=1)


class LLMResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


@runtime_checkable
class LLMGateway(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse: ...
