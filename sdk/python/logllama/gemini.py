from __future__ import annotations

from typing import Any

from .provider_instrumentation import instrument_provider_method


def wrap_gemini(gemini_client: Any, **kwargs: Any) -> Any:
    instrument_provider_method(
        gemini_client,
        path=("interactions",),
        method_name="create",
        provider="gemini",
        operation="interactions.create",
        prompt_keys=("input",),
        config_overrides=kwargs,
    )
    instrument_provider_method(
        gemini_client,
        path=("models",),
        method_name="generate_content",
        provider="gemini",
        operation="models.generate_content",
        prompt_keys=("contents",),
        config_overrides=kwargs,
    )
    instrument_provider_method(
        gemini_client,
        path=("aio", "interactions"),
        method_name="create",
        provider="gemini",
        operation="interactions.create",
        prompt_keys=("input",),
        config_overrides=kwargs,
    )
    instrument_provider_method(
        gemini_client,
        path=("aio", "models"),
        method_name="generate_content",
        provider="gemini",
        operation="models.generate_content",
        prompt_keys=("contents",),
        config_overrides=kwargs,
    )
    return gemini_client


instrument_gemini = wrap_gemini
track_gemini = wrap_gemini
