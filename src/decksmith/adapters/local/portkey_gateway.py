"""LLMGateway through Portkey (OSS gateway locally, Enterprise hybrid in production).

Uses the standard OpenAI SDK with Portkey headers, as in the design. The OSS gateway has no stored
configs, so the config JSON for each tier is sent inline in x-portkey-config.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import APIError, OpenAI

from decksmith.domain.errors import ConfigurationError, UpstreamError
from decksmith.ports.llm import LLMRequest, LLMResponse, Tier

KEY_PLACEHOLDER = "$DECKSMITH_LLM_API_KEY"


def _load_config(path: Path, provider_api_key: str) -> str:
    """Read a config, put the user's key into targets that ask for it, and compact it for a header.

    The OSS gateway needs ``api_key`` on every provider target, so a target that should use the
    user's own key says ``"api_key": "$DECKSMITH_LLM_API_KEY"``. The key is filled in here, in
    memory, and only ever sent to the local gateway; it is never written to a file. Header values
    cannot contain newlines, hence the compact dump.
    """
    config = json.loads(path.read_text())
    for target in config.get("targets", []):
        if target.get("api_key") == KEY_PLACEHOLDER:
            if not provider_api_key:
                raise ConfigurationError(f"{path.name} needs DECKSMITH_LLM_API_KEY (your provider key)")
            target["api_key"] = provider_api_key
    return json.dumps(config, separators=(",", ":"))


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
            tier: _load_config(config_dir / f"pc-deck-{tier}.json", provider_api_key) for tier in ("small", "strong")
        }
        self._client: Any = client or OpenAI(
            api_key="unused",
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
        try:
            response = self._client.chat.completions.create(**kwargs)
        except APIError as exc:
            # Status and type only: provider messages can echo part of the key.
            status = getattr(exc, "status_code", None)
            raise UpstreamError(f"LLM gateway call failed ({type(exc).__name__}, status {status})") from None
        usage = response.usage
        return LLMResponse(
            text=response.choices[0].message.content or "",
            model=response.model or "",
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )
