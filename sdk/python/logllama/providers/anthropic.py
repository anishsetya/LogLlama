from __future__ import annotations

from typing import Any

from .base import GenerationResponse, normalized_usage, read_value


class AnthropicAdapter:
    name = "anthropic"

    def __init__(self, client: Any):
        self.client = client

    def generate(
        self,
        *,
        prompt: str | None,
        messages: list[dict[str, Any]] | None,
        model: str,
        system: str | None,
        max_output_tokens: int | None,
        temperature: float | None,
        metadata: dict[str, Any] | None,
        provider_options: dict[str, Any] | None,
    ) -> GenerationResponse:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages or [{"role": "user", "content": prompt or ""}],
            "max_tokens": max_output_tokens or 1024,
            **dict(provider_options or {}),
        }
        if system is not None:
            payload["system"] = system
        if temperature is not None:
            payload["temperature"] = temperature
        if metadata and getattr(self.client.messages.create, "_logllama_wrapped", False):
            payload["logllama_metadata"] = metadata

        raw = self.client.messages.create(**payload)
        text = "".join(
            str(read_value(block, "text", ""))
            for block in (read_value(raw, "content", []) or [])
            if read_value(block, "type") in {None, "text"}
        )
        stop_reason = read_value(raw, "stop_reason")
        return GenerationResponse(
            text=text,
            provider=self.name,
            model=str(read_value(raw, "model", model) or model),
            usage=normalized_usage(raw),
            finish_reason=str(stop_reason) if stop_reason is not None else None,
            raw=raw,
        )
