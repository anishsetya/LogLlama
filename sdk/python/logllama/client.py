from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from urllib import request

from .config import LogLlamaConfig


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def monotonic_ms(start: float) -> int:
    return max(0, int((time.perf_counter() - start) * 1000))


def safe_json(value: Any) -> Any:
    if isinstance(value, Enum):
        return safe_json(value.value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [safe_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): safe_json(item) for key, item in value.items()}
    if hasattr(value, "model_dump"):
        return safe_json(value.model_dump())
    if hasattr(value, "dict"):
        return safe_json(value.dict())
    return repr(value)


def post_event_async(config: LogLlamaConfig, event: dict[str, Any]) -> None:
    if not config.enabled or not config.api_key:
        return

    thread = threading.Thread(target=_post_event, args=(config, event), daemon=True)
    thread.start()


def _post_event(config: LogLlamaConfig, event: dict[str, Any]) -> None:
    body = json.dumps(event, default=str).encode("utf-8")
    url = config.endpoint.rstrip("/") + "/v1/events"
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-LogLlama-Api-Key": config.api_key or "",
            "User-Agent": "logllama-python/0.1.0",
        },
    )

    try:
        with request.urlopen(req, timeout=config.timeout_seconds):
            return
    except Exception:
        return


def new_external_id() -> str:
    return f"llreq_{uuid.uuid4().hex}"
