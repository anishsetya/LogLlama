from __future__ import annotations

import functools
import inspect
import time
from typing import Any, Callable

from .client import monotonic_ms, new_external_id, now_iso, post_event_async
from .config import LogLlamaConfig, get_config
from .openai import (
    _build_event_metadata,
    _extract_response_model,
    _extract_usage,
    _prepare_capture,
    _should_capture,
)


def instrument_provider_method(
    client: Any,
    *,
    path: tuple[str, ...],
    method_name: str,
    provider: str,
    operation: str,
    prompt_keys: tuple[str, ...],
    config_overrides: dict[str, Any],
) -> None:
    target = client
    for part in path:
        target = getattr(target, part, None)
        if target is None:
            return
    original = getattr(target, method_name, None)
    if original is None or getattr(original, "_logllama_wrapped", False):
        return

    config = get_config(**config_overrides)
    if inspect.iscoroutinefunction(original):
        wrapped = _wrap_async(original, provider, operation, prompt_keys, config)
    else:
        wrapped = _wrap_sync(original, provider, operation, prompt_keys, config)
    setattr(target, method_name, wrapped)


def _wrap_sync(
    original: Callable[..., Any],
    provider: str,
    operation: str,
    prompt_keys: tuple[str, ...],
    config: LogLlamaConfig,
) -> Callable[..., Any]:
    @functools.wraps(original)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return _invoke_sync(original, args, kwargs, provider, operation, prompt_keys, config)

    wrapper._logllama_wrapped = True  # type: ignore[attr-defined]
    return wrapper


def _wrap_async(
    original: Callable[..., Any],
    provider: str,
    operation: str,
    prompt_keys: tuple[str, ...],
    config: LogLlamaConfig,
) -> Callable[..., Any]:
    @functools.wraps(original)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        external_id, start, model, prompt, metadata, should_capture = _before_call(
            kwargs, operation, prompt_keys, config
        )
        try:
            response = await original(*args, **kwargs)
        except Exception as exc:
            _capture_error(config, external_id, provider, operation, model, prompt, metadata, start, exc)
            raise
        _capture_success(
            config, external_id, provider, operation, model, prompt, metadata, start, response, should_capture
        )
        return response

    wrapper._logllama_wrapped = True  # type: ignore[attr-defined]
    return wrapper


def _invoke_sync(
    original: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    provider: str,
    operation: str,
    prompt_keys: tuple[str, ...],
    config: LogLlamaConfig,
) -> Any:
    external_id, start, model, prompt, metadata, should_capture = _before_call(
        kwargs, operation, prompt_keys, config
    )
    try:
        response = original(*args, **kwargs)
    except Exception as exc:
        _capture_error(config, external_id, provider, operation, model, prompt, metadata, start, exc)
        raise
    _capture_success(
        config, external_id, provider, operation, model, prompt, metadata, start, response, should_capture
    )
    return response


def _before_call(
    kwargs: dict[str, Any],
    operation: str,
    prompt_keys: tuple[str, ...],
    config: LogLlamaConfig,
) -> tuple[str, float, Any, Any, dict[str, Any], bool]:
    external_id = new_external_id()
    start = time.perf_counter()
    model = kwargs.get("model")
    logllama_metadata = kwargs.pop("logllama_metadata", None)
    prompt_value = next((kwargs.get(key) for key in prompt_keys if kwargs.get(key) is not None), None)
    prompt = _prepare_capture(prompt_value, config, "prompt")
    metadata = _build_event_metadata(config, kwargs, external_id, logllama_metadata)
    return external_id, start, model, prompt, metadata, _should_capture(config, metadata)


def _capture_error(
    config: LogLlamaConfig,
    external_id: str,
    provider: str,
    operation: str,
    model: Any,
    prompt: Any,
    metadata: dict[str, Any],
    start: float,
    exc: Exception,
) -> None:
    if not config.capture_errors:
        return
    post_event_async(
        config,
        {
            "external_id": external_id,
            "provider": provider,
            "operation": operation,
            "model": model,
            "status": "error",
            "prompt": prompt,
            "response": None,
            "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "latency_ms": monotonic_ms(start),
            "error": {"type": exc.__class__.__name__, "message": str(exc)},
            **metadata,
            "captured_at": now_iso(),
        },
    )


def _capture_success(
    config: LogLlamaConfig,
    external_id: str,
    provider: str,
    operation: str,
    model: Any,
    prompt: Any,
    metadata: dict[str, Any],
    start: float,
    response: Any,
    should_capture: bool,
) -> None:
    if not should_capture:
        return
    post_event_async(
        config,
        {
            "external_id": external_id,
            "provider": provider,
            "operation": operation,
            "model": _extract_response_model(response) or model,
            "status": "success",
            "prompt": prompt,
            "response": _prepare_capture(response, config, "response"),
            "usage": _extract_usage(response),
            "latency_ms": monotonic_ms(start),
            "error": None,
            **metadata,
            "captured_at": now_iso(),
        },
    )
