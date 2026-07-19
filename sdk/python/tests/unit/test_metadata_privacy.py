from __future__ import annotations

from typing import Any

import logllama
import logllama.openai as logllama_openai


class _Usage:
    prompt_tokens = 11
    completion_tokens = 7
    total_tokens = 18


class _Response:
    model = "gpt-test"
    usage = _Usage()

    def model_dump(self) -> dict[str, Any]:
        return {
            "model": "gpt-test",
            "content": "LogLlama metadata capture works.",
            "api_key": "response-secret",
        }


class _Completions:
    received_kwargs: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> _Response:
        self.received_kwargs = kwargs
        return _Response()


class _Chat:
    def __init__(self) -> None:
        self.completions = _Completions()


class _Client:
    def __init__(self) -> None:
        self.chat = _Chat()


def test_sdk_captures_realistic_metadata_and_privacy_controls(monkeypatch) -> None:
    events: list[dict[str, Any]] = []
    monkeypatch.setattr(logllama_openai, "post_event_async", lambda _config, event: events.append(event))

    client = logllama.wrap_openai(
        _Client(),
        api_key="test-logllama-key",
        service_name="checkout-api",
        environment="test",
        version="1.2.3",
        git_sha="abc123",
        tags=["checkout"],
        redact_keys=["api_key"],
        max_prompt_size=80,
        max_response_size=4000,
        sample_rate=1,
    )

    with logllama.context(
        route="/checkout/recommend",
        user_id="user_123",
        tenant_id="tenant_acme",
        session_id="sess_123",
        conversation_id="conv_123",
        request_id="req_123",
        trace_id="00000000000000000000000000000001",
        span_id="0000000000000001",
        prompt_template="cart_recommendation",
        prompt_version="v4",
    ):
        client.chat.completions.create(
            model="gpt-test",
            messages=[
                {
                    "role": "user",
                    "content": "Recommend accessories for a laptop bag using a concise answer.",
                    "api_key": "prompt-secret",
                }
            ],
            metadata={
                "provider_metadata": "openai-safe",
            },
            logllama_metadata={
                "tags": ["recommendations"],
                "custom_metadata": {"experiment": "metadata-capture-v1"},
            },
        )

    assert len(events) == 1
    event = events[0]
    assert event["service_name"] == "checkout-api"
    assert event["environment"] == "test"
    assert event["version"] == "1.2.3"
    assert event["git_sha"] == "abc123"
    assert event["route"] == "/checkout/recommend"
    assert event["user_id"] == "user_123"
    assert event["tenant_id"] == "tenant_acme"
    assert event["conversation_id"] == "conv_123"
    assert event["trace_id"] == "00000000000000000000000000000001"
    assert event["span_id"] == "0000000000000001"
    assert event["prompt_template"] == "cart_recommendation"
    assert event["prompt_version"] == "v4"
    assert event["tags"] == ["checkout", "recommendations"]
    assert event["custom_metadata"]["experiment"] == "metadata-capture-v1"
    assert event["prompt"]["_logllama_capture"] == "truncated"
    assert event["response"]["api_key"] == "[REDACTED]"
    assert event["usage"] == {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}
    assert "logllama_metadata" not in client.chat.completions.received_kwargs
