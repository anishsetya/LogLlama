import io
import json
from urllib import error

import pytest

from app.secret_store import VaultKvV2SecretStore, _credential_value


class FakeResponse:
    def __init__(self, payload=None):
        self._payload = json.dumps(payload).encode() if payload is not None else b""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self._payload


def test_vault_kv_v2_put_get_and_delete(monkeypatch):
    calls = []
    responses = iter(
        [
            FakeResponse(),
            FakeResponse({"data": {"data": {"value": "provider-key"}}}),
            FakeResponse(),
        ]
    )

    def fake_urlopen(req, timeout):
        calls.append((req, timeout))
        return next(responses)

    monkeypatch.setattr("app.secret_store.request.urlopen", fake_urlopen)
    store = VaultKvV2SecretStore(
        "http://127.0.0.1:8200/",
        "root-token",
        namespace="admin",
        timeout_seconds=0.5,
    )

    assert store.put("logllama/openai key", "provider-key") == "logllama/openai key"
    assert store.get("logllama/openai key") == "provider-key"
    store.delete("logllama/openai key")

    assert [call[0].method for call in calls] == ["POST", "GET", "DELETE"]
    assert calls[0][0].full_url.endswith("/v1/secret/data/logllama/openai%20key")
    assert calls[2][0].full_url.endswith("/v1/secret/metadata/logllama/openai%20key")
    assert calls[0][0].headers["X-vault-token"] == "root-token"
    assert calls[0][0].headers["X-vault-namespace"] == "admin"
    assert calls[0][1] == 0.5
    assert json.loads(calls[0][0].data) == {"data": {"value": "provider-key"}}


def test_vault_kv_v2_maps_not_found_to_key_error(monkeypatch):
    def fake_urlopen(req, timeout):
        raise error.HTTPError(req.full_url, 404, "not found", {}, io.BytesIO())

    monkeypatch.setattr("app.secret_store.request.urlopen", fake_urlopen)
    store = VaultKvV2SecretStore("http://127.0.0.1:8200", "root-token")

    with pytest.raises(KeyError):
        store.get("missing")


def test_vault_kv_v2_requires_https_for_remote_addresses():
    with pytest.raises(ValueError, match="must use HTTPS"):
        VaultKvV2SecretStore("http://vault.internal:8200", "root-token")


def test_vault_kv_v2_authenticates_with_approle(monkeypatch):
    calls = []
    responses = iter(
        [
            FakeResponse({"auth": {"client_token": "approle-token"}}),
            FakeResponse({"data": {"data": {"value": "provider-key"}}}),
        ]
    )

    def fake_urlopen(req, timeout):
        calls.append((req, timeout))
        return next(responses)

    monkeypatch.setattr("app.secret_store.request.urlopen", fake_urlopen)
    store = VaultKvV2SecretStore(
        "http://127.0.0.1:8200",
        role_id="role-id",
        secret_id="secret-id",
    )

    assert store.get("logllama/project/openai") == "provider-key"
    assert calls[0][0].full_url.endswith("/v1/auth/approle/login")
    assert json.loads(calls[0][0].data) == {
        "role_id": "role-id",
        "secret_id": "secret-id",
    }
    assert "X-vault-token" not in calls[0][0].headers
    assert calls[1][0].headers["X-vault-token"] == "approle-token"


def test_vault_kv_v2_reauthenticates_once_after_forbidden(monkeypatch):
    calls = []
    responses = iter(
        [
            FakeResponse({"auth": {"client_token": "first-token"}}),
            error.HTTPError("http://127.0.0.1:8200", 403, "forbidden", {}, io.BytesIO()),
            FakeResponse({"auth": {"client_token": "second-token"}}),
            FakeResponse({"data": {"data": {"value": "provider-key"}}}),
        ]
    )

    def fake_urlopen(req, timeout):
        calls.append((req, timeout))
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr("app.secret_store.request.urlopen", fake_urlopen)
    store = VaultKvV2SecretStore(
        "http://127.0.0.1:8200",
        role_id="role-id",
        secret_id="secret-id",
    )

    assert store.get("logllama/project/openai") == "provider-key"
    assert [call[0].full_url for call in calls].count(
        "http://127.0.0.1:8200/v1/auth/approle/login"
    ) == 2
    assert calls[-1][0].headers["X-vault-token"] == "second-token"


def test_credential_value_reads_secret_file(tmp_path):
    credential_file = tmp_path / "credential"
    credential_file.write_text(" file-secret \n", encoding="utf-8")

    assert _credential_value(None, str(credential_file), "credential") == "file-secret"
    assert _credential_value("explicit-secret", str(credential_file), "credential") == (
        "explicit-secret"
    )
