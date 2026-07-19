from app.config import DEFAULT_API_KEY, DEFAULT_DATABASE_URL, DEFAULT_PROJECT_NAME, Settings


def test_blank_environment_values_fall_back_to_dev_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("LOGLLAMA_DEFAULT_API_KEY", "")
    monkeypatch.setenv("LOGLLAMA_DEFAULT_PROJECT_NAME", "")

    settings = Settings()

    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.default_api_key == DEFAULT_API_KEY
    assert settings.default_project_name == DEFAULT_PROJECT_NAME
