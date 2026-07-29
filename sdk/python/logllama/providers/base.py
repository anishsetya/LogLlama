from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True, slots=True)
class GenerationResponse:
    text: str
    provider: str
    model: str
    usage: Usage
    finish_reason: str | None
    raw: Any


class ProviderAdapter(Protocol):
    name: str

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
    ) -> GenerationResponse: ...


def read_value(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def normalized_usage(raw: Any) -> Usage:
    usage = read_value(raw, "usage")
    input_tokens = _int_value(usage, "input_tokens", "prompt_tokens")
    output_tokens = _int_value(usage, "output_tokens", "completion_tokens")
    total_tokens = _int_value(usage, "total_tokens")
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens or input_tokens + output_tokens,
    )


def _int_value(value: Any, *names: str) -> int:
    for name in names:
        item = read_value(value, name)
        if item is not None:
            try:
                return int(item)
            except (TypeError, ValueError):
                return 0
    return 0
