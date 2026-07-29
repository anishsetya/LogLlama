from __future__ import annotations

from typing import Any

from .base import GenerationResponse, normalized_usage, read_value


class OpenAIAdapter:
    name = "openai"

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
        options = dict(provider_options or {})
        if getattr(self.client, "responses", None) is not None:
            payload: dict[str, Any] = {
                "model": model,
                "input": messages if messages is not None else prompt or "",
                **options,
            }
            if system is not None:
                payload["instructions"] = system
            if max_output_tokens is not None:
                payload["max_output_tokens"] = max_output_tokens
            if temperature is not None:
                payload["temperature"] = temperature
            if metadata and getattr(self.client.responses.create, "_logllama_wrapped", False):
                payload["logllama_metadata"] = metadata
            raw = self.client.responses.create(**payload)
            text = str(read_value(raw, "output_text", "") or _responses_text(raw))
        else:
            chat_messages = list(messages or [{"role": "user", "content": prompt or ""}])
            if system is not None:
                chat_messages.insert(0, {"role": "system", "content": system})
            payload = {"model": model, "messages": chat_messages, **options}
            if max_output_tokens is not None:
                payload["max_tokens"] = max_output_tokens
            if temperature is not None:
                payload["temperature"] = temperature
            if metadata and getattr(self.client.chat.completions.create, "_logllama_wrapped", False):
                payload["logllama_metadata"] = metadata
            raw = self.client.chat.completions.create(**payload)
            choices = read_value(raw, "choices", []) or []
            message = read_value(choices[0], "message") if choices else None
            text = str(read_value(message, "content", "") or "")

        return GenerationResponse(
            text=text,
            provider=self.name,
            model=str(read_value(raw, "model", model) or model),
            usage=normalized_usage(raw),
            finish_reason=_finish_reason(raw),
            raw=raw,
        )


def _responses_text(raw: Any) -> str:
    text_parts: list[str] = []
    for output in read_value(raw, "output", []) or []:
        for content in read_value(output, "content", []) or []:
            text = read_value(content, "text")
            if text:
                text_parts.append(str(text))
    return "".join(text_parts)


def _finish_reason(raw: Any) -> str | None:
    choices = read_value(raw, "choices", []) or []
    if choices:
        reason = read_value(choices[0], "finish_reason")
        return str(reason) if reason is not None else None
    status = read_value(raw, "status")
    return str(status) if status is not None else None
