from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class LogLlamaConfig:
    api_key: str | None = None
    endpoint: str = "http://localhost:8000"
    timeout_seconds: float = 1.0
    capture_prompts: bool = True
    capture_responses: bool = True
    enabled: bool = True


_config = LogLlamaConfig()
_env_loaded = False


def init(
    api_key: str | None = None,
    endpoint: str | None = None,
    timeout_seconds: float | None = None,
    capture_prompts: bool | None = None,
    capture_responses: bool | None = None,
    enabled: bool | None = None,
) -> LogLlamaConfig:
    """Configure LogLlama once for the current Python process."""
    global _config

    env_config = config_from_env()
    updates: dict[str, Any] = {
        "api_key": api_key if api_key is not None else env_config.api_key,
        "endpoint": endpoint if endpoint is not None else env_config.endpoint,
        "timeout_seconds": timeout_seconds if timeout_seconds is not None else env_config.timeout_seconds,
        "capture_prompts": capture_prompts if capture_prompts is not None else env_config.capture_prompts,
        "capture_responses": capture_responses if capture_responses is not None else env_config.capture_responses,
        "enabled": enabled if enabled is not None else env_config.enabled,
    }
    _config = replace(_config, **updates)
    return _config


def get_config(**overrides: Any) -> LogLlamaConfig:
    config = config_from_env()
    for key, value in overrides.items():
        if value is not None:
            config = replace(config, **{key: value})
    return config


def config_from_env() -> LogLlamaConfig:
    load_dotenv()
    return LogLlamaConfig(
        api_key=os.getenv("LOGLLAMA_API_KEY") or _config.api_key,
        endpoint=os.getenv("LOGLLAMA_ENDPOINT") or _config.endpoint,
        timeout_seconds=_float_env("LOGLLAMA_TIMEOUT_SECONDS", _config.timeout_seconds),
        capture_prompts=_bool_env("LOGLLAMA_CAPTURE_PROMPTS", _config.capture_prompts),
        capture_responses=_bool_env("LOGLLAMA_CAPTURE_RESPONSES", _config.capture_responses),
        enabled=_bool_env("LOGLLAMA_ENABLED", _config.enabled),
    )


def load_dotenv(path: str | Path | None = None) -> None:
    """Load simple KEY=VALUE pairs from .env without requiring python-dotenv."""
    global _env_loaded
    if _env_loaded and path is None:
        return

    env_path = Path(path) if path else _find_dotenv()
    if env_path is None or not env_path.exists():
        _env_loaded = True
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

    _env_loaded = True


def _find_dotenv() -> Path | None:
    current = Path.cwd()
    for directory in (current, *current.parents):
        candidate = directory / ".env"
        if candidate.exists():
            return candidate
    return None


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default

