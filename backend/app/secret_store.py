from __future__ import annotations

import json
import threading
from pathlib import Path
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
        token: str | None = None,
        mount: str = "secret",
        namespace: str | None = None,
        timeout_seconds: float = 2.0,
        role_id: str | None = None,
        secret_id: str | None = None,
    ) -> None:
        if not token and not (role_id and secret_id):
            raise ValueError("A secret-store token or AppRole credentials are required.")
        if bool(role_id) != bool(secret_id):
            raise ValueError("Both AppRole role_id and secret_id are required.")
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
        self._role_id = role_id
        self._secret_id = secret_id
        self._mount = parse.quote(mount.strip("/"), safe="")
        self._namespace = namespace
        self._timeout_seconds = timeout_seconds
        self._auth_lock = threading.Lock()

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
        token = self._current_token()
        try:
            return self._request_once(method, url, payload, token)
        except error.HTTPError as exc:
            if exc.code != 403 or not self._role_id:
                raise self._mapped_http_error(exc) from exc
        with self._auth_lock:
            if self._token == token:
                self._token = None
        try:
            return self._request_once(method, url, payload, self._current_token())
        except error.HTTPError as exc:
            raise self._mapped_http_error(exc) from exc

    def _request_once(
        self,
        method: str,
        url: str,
        payload: dict | None,
        token: str,
    ) -> dict:
        headers = {
            "Content-Type": "application/json",
            "X-Vault-Token": token,
        }
        if self._namespace:
            headers["X-Vault-Namespace"] = self._namespace
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = request.Request(url, data=body, method=method, headers=headers)
        try:
            with request.urlopen(req, timeout=self._timeout_seconds) as response:
                raw = response.read()
        except error.HTTPError as exc:
            raise
        except error.URLError as exc:
            raise RuntimeError("Secret store is unavailable.") from exc
        return self._decode_response(raw)

    def _current_token(self) -> str:
        if self._token:
            return self._token
        with self._auth_lock:
            if self._token:
                return self._token
            self._token = self._login_approle()
            return self._token

    def _login_approle(self) -> str:
        if not self._role_id or not self._secret_id:
            raise RuntimeError("Secret-store authentication is not configured.")
        headers = {"Content-Type": "application/json"}
        if self._namespace:
            headers["X-Vault-Namespace"] = self._namespace
        body = json.dumps(
            {"role_id": self._role_id, "secret_id": self._secret_id}
        ).encode("utf-8")
        req = request.Request(
            f"{self._addr}/v1/auth/approle/login",
            data=body,
            method="POST",
            headers=headers,
        )
        try:
            with request.urlopen(req, timeout=self._timeout_seconds) as response:
                payload = self._decode_response(response.read())
        except error.HTTPError as exc:
            raise RuntimeError(
                f"Secret-store AppRole login failed with HTTP {exc.code}."
            ) from exc
        except error.URLError as exc:
            raise RuntimeError("Secret store is unavailable.") from exc
        try:
            token = payload["auth"]["client_token"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError("Secret-store AppRole login returned no token.") from exc
        if not isinstance(token, str) or not token:
            raise RuntimeError("Secret-store AppRole login returned no token.")
        return token

    def _mapped_http_error(self, exc: error.HTTPError) -> Exception:
        if exc.code == 404:
            return KeyError(exc.url.rsplit("/", 1)[-1])
        return RuntimeError(f"Secret store request failed with HTTP {exc.code}.")

    @staticmethod
    def _decode_response(raw: bytes) -> dict:
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
                token = _credential_value(
                    settings.secret_store_token,
                    settings.secret_store_token_file,
                    "secret-store token",
                )
                role_id = None
                secret_id = None
                if not token:
                    role_id = _credential_value(
                        settings.secret_store_role_id,
                        settings.secret_store_role_id_file,
                        "AppRole role ID",
                    )
                    secret_id = _credential_value(
                        settings.secret_store_secret_id,
                        settings.secret_store_secret_id_file,
                        "AppRole secret ID",
                    )
                _store = VaultKvV2SecretStore(
                    addr=settings.secret_store_addr,
                    token=token,
                    mount=settings.secret_store_mount,
                    namespace=settings.secret_store_namespace,
                    timeout_seconds=settings.secret_store_timeout_seconds,
                    role_id=role_id,
                    secret_id=secret_id,
                )
            else:
                _store = _memory_store
    return _store


def _credential_value(
    explicit_value: str | None,
    file_name: str | None,
    label: str,
) -> str | None:
    if explicit_value:
        return explicit_value.strip()
    if not file_name:
        return None
    path = Path(file_name).expanduser()
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Unable to read {label} file '{path}'.") from exc
    if not value:
        raise RuntimeError(f"{label.capitalize()} file '{path}' is empty.")
    return value
