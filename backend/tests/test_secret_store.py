import io
import json
from urllib import error

import pytest

from app.secret_store import VaultKvV2SecretStore


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
