from app.config import (
    DEFAULT_API_KEY,
    DEFAULT_DATABASE_URL,
    DEFAULT_PROJECT_NAME,
    DEFAULT_RUNTIME_KEY,
    Settings,
)
import pytest


def test_blank_environment_values_fall_back_to_dev_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("LOGLLAMA_DEFAULT_API_KEY", "")
    monkeypatch.setenv("LOGLLAMA_DEFAULT_RUNTIME_KEY", "")
    monkeypatch.setenv("LOGLLAMA_DEFAULT_PROJECT_NAME", "")

    settings = Settings()

    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.default_api_key == DEFAULT_API_KEY
    assert settings.default_runtime_key == DEFAULT_RUNTIME_KEY
    assert settings.default_project_name == DEFAULT_PROJECT_NAME


@pytest.mark.parametrize("backend", ["memory", "aws", "vault", "openbao"])
def test_supported_secret_backends(backend):
    settings = Settings(LOGLLAMA_SECRET_BACKEND=backend)

    assert settings.secret_backend == backend


def test_vault_conventional_environment_aliases(monkeypatch):
    monkeypatch.setenv("VAULT_ADDR", "http://vault.internal:8200")
    monkeypatch.setenv("VAULT_TOKEN", "test-token")
    monkeypatch.delenv("LOGLLAMA_SECRET_STORE_ADDR", raising=False)
    monkeypatch.delenv("LOGLLAMA_SECRET_STORE_TOKEN", raising=False)

    settings = Settings()

    assert settings.secret_store_addr == "http://vault.internal:8200"
    assert settings.secret_store_token == "test-token"
