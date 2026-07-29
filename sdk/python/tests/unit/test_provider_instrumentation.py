from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import logllama
import logllama.provider_instrumentation as instrumentation


class _Messages:
    received: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> Any:
        self.received = kwargs
        return SimpleNamespace(
            model=kwargs["model"],
            content=[SimpleNamespace(type="text", text="ok")],
            usage=SimpleNamespace(input_tokens=2, output_tokens=1),
        )


class _Anthropic:
    def __init__(self) -> None:
        self.messages = _Messages()


class _Models:
    received: dict[str, Any] | None = None

    def generate_content(self, **kwargs: Any) -> Any:
        self.received = kwargs
        return SimpleNamespace(
            text="ok",
            usage_metadata=SimpleNamespace(
                prompt_token_count=3,
                candidates_token_count=2,
                total_token_count=5,
            ),
        )


class _Gemini:
    def __init__(self) -> None:
        self.models = _Models()


def test_anthropic_wrapper_captures_and_removes_logllama_metadata(monkeypatch) -> None:
    events: list[dict[str, Any]] = []
    monkeypatch.setattr(instrumentation, "post_event_async", lambda _config, event: events.append(event))
    client = logllama.wrap_anthropic(
        _Anthropic(),
        api_key="logllama-key",
        capture_otel=False,
    )

    client.messages.create(
        model="claude-test",
        max_tokens=10,
        messages=[{"role": "user", "content": "hello"}],
        logllama_metadata={"tenant_id": "tenant-test"},
    )

    assert client.messages.received is not None
    assert "logllama_metadata" not in client.messages.received
    assert events[0]["provider"] == "anthropic"
    assert events[0]["tenant_id"] == "tenant-test"
    assert events[0]["usage"]["total_tokens"] == 3


def test_gemini_wrapper_normalizes_usage(monkeypatch) -> None:
    events: list[dict[str, Any]] = []
    monkeypatch.setattr(instrumentation, "post_event_async", lambda _config, event: events.append(event))
    client = logllama.wrap_gemini(
        _Gemini(),
        api_key="logllama-key",
        capture_otel=False,
    )

    client.models.generate_content(
        model="gemini-test",
        contents="hello",
        logllama_metadata={"comparison_id": "cmp-test"},
    )

    assert events[0]["provider"] == "gemini"
    assert events[0]["usage"] == {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}
    assert events[0]["custom_metadata"]["comparison_id"] == "cmp-test"
