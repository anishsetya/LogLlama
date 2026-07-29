from __future__ import annotations

import json
import threading
from collections.abc import Callable
from typing import Any
from urllib import request


class ManagedCredentialCache:
    """Preloads managed credentials and refreshes them outside the request path."""

    def __init__(
        self,
        *,
        endpoint: str,
        runtime_key: str,
        timeout_seconds: float = 3.0,
        refresh_seconds: float = 300.0,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.runtime_key = runtime_key
        self.timeout_seconds = timeout_seconds
        self.refresh_seconds = max(5.0, refresh_seconds)
        self._credentials: dict[str, str] = {}
        self._versions: dict[str, str] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def get(self, provider: str) -> str | None:
        return self._credentials.get(_normalize_provider(provider))

    def snapshot(self) -> dict[str, str]:
        return dict(self._credentials)

    def prefetch(self) -> set[str]:
        credentials, versions = self._fetch()
        changed = {
            provider
            for provider in set(self._versions) | set(versions)
            if self._versions.get(provider) != versions.get(provider)
        }
        self._credentials = credentials
        self._versions = versions
        return changed

    def start_background_refresh(
        self,
        on_change: Callable[[set[str], dict[str, str]], None] | None = None,
    ) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._refresh_loop,
            args=(on_change,),
            name="logllama-credential-refresh",
            daemon=True,
        )
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=min(1.0, self.timeout_seconds))

    def _refresh_loop(
        self,
        on_change: Callable[[set[str], dict[str, str]], None] | None,
    ) -> None:
        while not self._stop.wait(self.refresh_seconds):
            try:
                changed = self.prefetch()
                if changed and on_change:
                    on_change(changed, self.snapshot())
            except Exception:
                # Keep the last-known-good credentials when the control plane is unavailable.
                continue

    def _fetch(self) -> tuple[dict[str, str], dict[str, str]]:
        req = request.Request(
            f"{self.endpoint}/v1/runtime/provider-credentials",
            headers={
                "X-LogLlama-Runtime-Key": self.runtime_key,
                "User-Agent": "logllama-python/0.2.0",
            },
        )
        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))

        credentials: dict[str, str] = {}
        versions: dict[str, str] = {}
        for item in payload.get("credentials", []):
            provider = _normalize_provider(str(item["provider"]))
            credentials[provider] = str(item["api_key"])
            versions[provider] = str(item.get("version") or item.get("updated_at") or "")
        return credentials, versions


def _normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    return "anthropic" if normalized == "claude" else normalized
