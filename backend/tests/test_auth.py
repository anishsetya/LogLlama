import asyncio

import pytest
from fastapi import HTTPException

from app import main


def run(coroutine):
    return asyncio.run(coroutine)


def test_admin_api_is_disabled_without_explicit_key(monkeypatch):
    monkeypatch.setattr(main.settings, "admin_api_key", None)

    with pytest.raises(HTTPException) as error:
        run(main.require_admin(None))

    assert error.value.status_code == 503


def test_admin_api_accepts_only_configured_key(monkeypatch):
    admin_key = "a" * 32
    monkeypatch.setattr(main.settings, "admin_api_key", admin_key)

    with pytest.raises(HTTPException) as error:
        run(main.require_admin("wrong-key"))

    assert error.value.status_code == 401
    assert run(main.require_admin(admin_key)) is None


@pytest.mark.parametrize("runtime_key", ["llama-runtime-key", "short-custom-key"])
def test_insecure_runtime_keys_are_rejected_before_database_lookup(runtime_key):
    with pytest.raises(HTTPException) as error:
        run(main.project_from_runtime_key(runtime_key, object()))

    assert error.value.status_code == 401
