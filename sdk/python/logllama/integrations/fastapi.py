from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from logllama.config import context


MetadataGetter = Callable[[Any], str | None]


class LogLlamaMiddleware:
    """Attach FastAPI request context to LogLlama events emitted inside the request."""

    def __init__(
        self,
        app: Callable[[Any, Any, Any], Awaitable[None]],
        service_name: str | None = None,
        environment: str | None = None,
        get_user_id: MetadataGetter | None = None,
        get_tenant_id: MetadataGetter | None = None,
        get_session_id: MetadataGetter | None = None,
    ) -> None:
        self.app = app
        self.service_name = service_name
        self.environment = environment
        self.get_user_id = get_user_id
        self.get_tenant_id = get_tenant_id
        self.get_session_id = get_session_id

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        request = _RequestView(scope)
        route = scope.get("route")
        route_path = getattr(route, "path", None) or scope.get("path")
        metadata = {
            "service_name": self.service_name,
            "environment": self.environment,
            "route": route_path,
            "request_id": _header(scope, "x-request-id") or str(uuid4()),
            "user_id": self.get_user_id(request) if self.get_user_id else None,
            "tenant_id": self.get_tenant_id(request) if self.get_tenant_id else None,
            "session_id": self.get_session_id(request) if self.get_session_id else None,
            "custom_metadata": {
                "http_method": scope.get("method"),
            },
        }
        with context(**metadata):
            await self.app(scope, receive, send)


class _RequestView:
    def __init__(self, scope: dict[str, Any]) -> None:
        self.scope = scope
        self.state = scope.get("state")
        self.path_params = scope.get("path_params", {})
        self.query_string = scope.get("query_string", b"")
        self.headers = {
            key.decode("latin1").lower(): value.decode("latin1")
            for key, value in scope.get("headers", [])
        }


def _header(scope: dict[str, Any], name: str) -> str | None:
    target = name.lower().encode("latin1")
    for key, value in scope.get("headers", []):
        if key.lower() == target:
            return value.decode("latin1")
    return None
