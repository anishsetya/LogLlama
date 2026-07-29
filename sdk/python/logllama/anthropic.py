from __future__ import annotations

from typing import Any

from .provider_instrumentation import instrument_provider_method


def wrap_anthropic(anthropic_client: Any, **kwargs: Any) -> Any:
    instrument_provider_method(
        anthropic_client,
        path=("messages",),
        method_name="create",
        provider="anthropic",
        operation="messages.create",
        prompt_keys=("messages",),
        config_overrides=kwargs,
    )
    return anthropic_client


instrument_anthropic = wrap_anthropic
track_anthropic = wrap_anthropic
