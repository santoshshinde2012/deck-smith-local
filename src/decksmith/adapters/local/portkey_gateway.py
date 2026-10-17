"""LLMGateway through Portkey (OSS gateway locally, Enterprise hybrid in production).

Uses the standard OpenAI SDK with Portkey headers, as in the design. The OSS gateway has no stored
configs, so the config JSON for each tier is sent inline in x-portkey-config.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from decksmith.ports.llm import LLMRequest, LLMResponse, Tier


class PortkeyGateway:
    def __init__(
        self,
        base_url: str,
        config_dir: Path,
        api_key: str = "local",
        app: str = "decksmith",
        env: str = "local",
        client: Any = None,
        provider_api_key: str = "",
    ) -> None:
        self._configs: dict[Tier, str] = {
            "small": (config_dir / "pc-deck-small.json").read_text(),
            "strong": (config_dir / "pc-deck-strong.json").read_text(),
        }
        self._client: Any = client or OpenAI(
            # The OSS gateway forwards the bearer token to the provider when a config target has no
            # key of its own, so a user's own provider key (e.g. OpenAI) never lands in a file.
            api_key=provider_api_key or "unused",
            base_url=base_url.rstrip("/") + "/v1",
            default_headers={"x-portkey-api-key": api_key},
        )
        self._app, self._env = app, env

    def complete(self, request: LLMRequest) -> LLMResponse:
        metadata = {
            "_user": request.user_hash,
            "app": self._app,
            "env": self._env,
            "run_id": request.run_id,
            "node": request.node,
        }
        kwargs: dict[str, Any] = {
            "model": "routed-by-portkey-config",
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "extra_headers": {
                "x-portkey-config": self._configs[request.tier],
                "x-portkey-metadata": json.dumps(metadata),
            },
        }
        if request.json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = self._client.chat.completions.create(**kwargs)
        usage = response.usage
        return LLMResponse(
            text=response.choices[0].message.content or "",
            model=response.model or "",
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )
