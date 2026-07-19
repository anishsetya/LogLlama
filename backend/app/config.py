from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_DATABASE_URL = "postgresql+asyncpg://logllama:logllama@localhost:5432/logllama"
DEFAULT_API_KEY = "llama-dev-key"
DEFAULT_PROJECT_NAME = "Development"


class Settings(BaseSettings):
    database_url: str = Field(
        default=DEFAULT_DATABASE_URL,
        validation_alias="DATABASE_URL",
    )
    default_api_key: str = Field(default=DEFAULT_API_KEY, validation_alias="LOGLLAMA_DEFAULT_API_KEY")
    default_project_name: str = Field(default=DEFAULT_PROJECT_NAME, validation_alias="LOGLLAMA_DEFAULT_PROJECT_NAME")
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @field_validator("database_url", "default_api_key", "default_project_name", mode="before")
    @classmethod
    def blank_string_uses_default(cls, value: Any, info):
        if not isinstance(value, str) or value.strip():
            return value
        defaults = {
            "database_url": DEFAULT_DATABASE_URL,
            "default_api_key": DEFAULT_API_KEY,
            "default_project_name": DEFAULT_PROJECT_NAME,
        }
        return defaults[info.field_name]


settings = Settings()
