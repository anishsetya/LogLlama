from __future__ import annotations

import json
import threading
from typing import Protocol
from urllib import error, parse, request

from .config import settings


class SecretStore(Protocol):
    def put(self, reference: str, value: str) -> str: ...

    def get(self, reference: str) -> str: ...

    def delete(self, reference: str) -> None: ...


class MemorySecretStore:
    """Development-only store. Production deployments should use a persistent backend."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self._lock = threading.Lock()

    def put(self, reference: str, value: str) -> str:
        with self._lock:
            self._values[reference] = value
        return reference

    def get(self, reference: str) -> str:
        with self._lock:
            value = self._values.get(reference)
        if value is None:
            raise KeyError(reference)
        return value

    def delete(self, reference: str) -> None:
        with self._lock:
            self._values.pop(reference, None)


class AwsSecretStore:
    def __init__(self, region_name: str | None = None) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("Install boto3 to use LOGLLAMA_SECRET_BACKEND=aws.") from exc
        self._client = boto3.client("secretsmanager", region_name=region_name)

    def put(self, reference: str, value: str) -> str:
        try:
            self._client.put_secret_value(SecretId=reference, SecretString=value)
        except self._client.exceptions.ResourceNotFoundException:
            self._client.create_secret(Name=reference, SecretString=value)
        return reference

    def get(self, reference: str) -> str:
        response = self._client.get_secret_value(SecretId=reference)
        value = response.get("SecretString")
        if not value:
            raise KeyError(reference)
        return str(value)

    def delete(self, reference: str) -> None:
        self._client.delete_secret(SecretId=reference, RecoveryWindowInDays=7)


class VaultKvV2SecretStore:
    """Minimal KV v2 client compatible with both HashiCorp Vault and OpenBao."""

    def __init__(
        self,
        addr: str,
        token: str,
        mount: str = "secret",
        namespace: str | None = None,
        timeout_seconds: float = 2.0,
    ) -> None:
        if not token:
            raise ValueError("A secret-store token is required.")
        parsed_addr = parse.urlparse(addr)
        if parsed_addr.scheme not in {"http", "https"} or not parsed_addr.hostname:
            raise ValueError("Secret-store address must be an HTTP(S) URL.")
        if parsed_addr.scheme == "http" and parsed_addr.hostname not in {
            "127.0.0.1",
            "::1",
            "localhost",
        }:
            raise ValueError("Remote secret-store addresses must use HTTPS.")
        self._addr = addr.rstrip("/")
        self._token = token
        self._mount = parse.quote(mount.strip("/"), safe="")
        self._namespace = namespace
        self._timeout_seconds = timeout_seconds

    def put(self, reference: str, value: str) -> str:
        self._request(
            "POST",
            self._url("data", reference),
            {"data": {"value": value}},
        )
        return reference

    def get(self, reference: str) -> str:
        payload = self._request("GET", self._url("data", reference))
        try:
            value = payload["data"]["data"]["value"]
        except (KeyError, TypeError) as exc:
            raise KeyError(reference) from exc
        if not isinstance(value, str) or not value:
            raise KeyError(reference)
        return value

    def delete(self, reference: str) -> None:
        # Deleting metadata permanently removes all versions and avoids stale test/admin records.
        self._request("DELETE", self._url("metadata", reference))

    def _url(self, resource: str, reference: str) -> str:
        path = parse.quote(reference.strip("/"), safe="/")
        return f"{self._addr}/v1/{self._mount}/{resource}/{path}"

    def _request(
        self,
        method: str,
        url: str,
        payload: dict | None = None,
    ) -> dict:
        headers = {
            "Content-Type": "application/json",
            "X-Vault-Token": self._token,
        }
        if self._namespace:
            headers["X-Vault-Namespace"] = self._namespace
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = request.Request(url, data=body, method=method, headers=headers)
        try:
            with request.urlopen(req, timeout=self._timeout_seconds) as response:
                raw = response.read()
        except error.HTTPError as exc:
            if exc.code == 404:
                raise KeyError(url.rsplit("/", 1)[-1]) from exc
            raise RuntimeError(f"Secret store request failed with HTTP {exc.code}.") from exc
        except error.URLError as exc:
            raise RuntimeError("Secret store is unavailable.") from exc
        if not raw:
            return {}
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Secret store returned an invalid JSON response.") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("Secret store returned an unexpected response.")
        return decoded


_memory_store = MemorySecretStore()
_store: SecretStore | None = None
_store_lock = threading.Lock()


def get_secret_store() -> SecretStore:
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is None:
            if settings.secret_backend == "aws":
                _store = AwsSecretStore(settings.aws_region)
            elif settings.secret_backend in {"vault", "openbao"}:
                if not settings.secret_store_token:
                    raise RuntimeError(
                        "LOGLLAMA_SECRET_STORE_TOKEN is required for Vault or OpenBao."
                    )
                _store = VaultKvV2SecretStore(
                    addr=settings.secret_store_addr,
                    token=settings.secret_store_token,
                    mount=settings.secret_store_mount,
                    namespace=settings.secret_store_namespace,
                    timeout_seconds=settings.secret_store_timeout_seconds,
                )
            else:
                _store = _memory_store
    return _store
