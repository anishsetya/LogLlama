from __future__ import annotations

import functools
import time
from typing import Any, Callable

from .client import monotonic_ms, new_external_id, now_iso, post_event_async, safe_json
from .config import LogLlamaConfig, get_config


def wrap_openai(openai_client: Any, **kwargs: Any) -> Any:
    return instrument_openai(openai_client, **kwargs)


def track_openai(openai_client: Any, **kwargs: Any) -> Any:
    return instrument_openai(openai_client, **kwargs)


def instrument_openai(
    openai_client: Any,
    api_key: str | None = None,
    endpoint: str | None = None,
    timeout_seconds: float | None = None,
    capture_prompts: bool | None = None,
    capture_responses: bool | None = None,
    enabled: bool | None = None,
) -> Any:
    config = get_config(
        api_key=api_key,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        capture_prompts=capture_prompts,
        capture_responses=capture_responses,
        enabled=enabled,
    )

    _wrap_path(openai_client, ("chat", "completions"), "create", "chat.completions.create", config)
    _wrap_path(openai_client, ("responses",), "create", "responses.create", config)
    return openai_client


def _wrap_path(root: Any, path: tuple[str, ...], method_name: str, operation: str, config: LogLlamaConfig) -> None:
    target = root
    for part in path:
        target = getattr(target, part, None)
        if target is None:
            return

    original = getattr(target, method_name, None)
    if original is None or getattr(original, "_logllama_wrapped", False):
        return

    wrapped = _wrap_call(original, operation, config)
    setattr(target, method_name, wrapped)


def _wrap_call(original: Callable[..., Any], operation: str, config: LogLlamaConfig) -> Callable[..., Any]:
    @functools.wraps(original)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        external_id = new_external_id()
        start = time.perf_counter()
        model = kwargs.get("model")
        prompt = _extract_prompt(operation, kwargs) if config.capture_prompts else None

        try:
            response = original(*args, **kwargs)
        except Exception as exc:
            post_event_async(
                config,
                {
                    "external_id": external_id,
                    "provider": "openai",
                    "operation": operation,
                    "model": model,
                    "status": "error",
                    "prompt": prompt,
                    "response": None,
                    "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                    "latency_ms": monotonic_ms(start),
                    "error": {"type": exc.__class__.__name__, "message": str(exc)},
                    "metadata": _extract_metadata(kwargs),
                    "captured_at": now_iso(),
                },
            )
            raise

        usage = _extract_usage(response)
        response_model = _extract_response_model(response) or model
        post_event_async(
            config,
            {
                "external_id": external_id,
                "provider": "openai",
                "operation": operation,
                "model": response_model,
                "status": "success",
                "prompt": prompt,
                "response": safe_json(response) if config.capture_responses else None,
                "usage": usage,
                "latency_ms": monotonic_ms(start),
                "error": None,
                "metadata": _extract_metadata(kwargs),
                "captured_at": now_iso(),
            },
        )
        return response

    wrapper._logllama_wrapped = True  # type: ignore[attr-defined]
    return wrapper


def _extract_prompt(operation: str, kwargs: dict[str, Any]) -> Any:
    if operation == "responses.create":
        return safe_json(kwargs.get("input"))
    return safe_json(kwargs.get("messages") or kwargs.get("prompt"))


def _extract_metadata(kwargs: dict[str, Any]) -> dict[str, Any]:
    metadata = kwargs.get("metadata")
    if isinstance(metadata, dict):
        return safe_json(metadata)
    return {}


def _extract_response_model(response: Any) -> str | None:
    model = getattr(response, "model", None)
    if model:
        return str(model)
    if isinstance(response, dict) and response.get("model"):
        return str(response["model"])
    return None


def _extract_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")

    input_tokens = _get_usage_value(usage, "prompt_tokens", "input_tokens")
    output_tokens = _get_usage_value(usage, "completion_tokens", "output_tokens")
    total_tokens = _get_usage_value(usage, "total_tokens")
    if not total_tokens:
        total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _get_usage_value(usage: Any, *names: str) -> int:
    if usage is None:
        return 0
    for name in names:
        value = getattr(usage, name, None)
        if value is None and isinstance(usage, dict):
            value = usage.get(name)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
    return 0

