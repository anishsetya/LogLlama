from typing import Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_DATABASE_URL = "postgresql+asyncpg://logllama:logllama@localhost:5432/logllama"
DEFAULT_API_KEY = "llama-dev-key"
DEFAULT_RUNTIME_KEY = "llama-runtime-key"
DEFAULT_PROJECT_NAME = "Development"


class Settings(BaseSettings):
    database_url: str = Field(
        default=DEFAULT_DATABASE_URL,
        validation_alias="DATABASE_URL",
    )
    default_api_key: str = Field(default=DEFAULT_API_KEY, validation_alias="LOGLLAMA_DEFAULT_API_KEY")
    default_runtime_key: str = Field(
        default=DEFAULT_RUNTIME_KEY, validation_alias="LOGLLAMA_DEFAULT_RUNTIME_KEY"
    )
    default_project_name: str = Field(default=DEFAULT_PROJECT_NAME, validation_alias="LOGLLAMA_DEFAULT_PROJECT_NAME")
    admin_api_key: str = Field(default="llama-admin-key", validation_alias="LOGLLAMA_ADMIN_API_KEY")
    secret_backend: str = Field(default="memory", validation_alias="LOGLLAMA_SECRET_BACKEND")
    secret_prefix: str = Field(default="logllama", validation_alias="LOGLLAMA_SECRET_PREFIX")
    aws_region: str | None = Field(default=None, validation_alias="AWS_REGION")
    secret_store_addr: str = Field(
        default="http://127.0.0.1:8200",
        validation_alias=AliasChoices(
            "LOGLLAMA_SECRET_STORE_ADDR",
            "VAULT_ADDR",
            "BAO_ADDR",
        ),
    )
    secret_store_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LOGLLAMA_SECRET_STORE_TOKEN",
            "VAULT_TOKEN",
            "BAO_TOKEN",
        ),
    )
    secret_store_mount: str = Field(
        default="secret",
        validation_alias="LOGLLAMA_SECRET_STORE_MOUNT",
    )
    secret_store_namespace: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LOGLLAMA_SECRET_STORE_NAMESPACE",
            "VAULT_NAMESPACE",
        ),
    )
    secret_store_timeout_seconds: float = Field(
        default=2.0,
        gt=0,
        validation_alias="LOGLLAMA_SECRET_STORE_TIMEOUT_SECONDS",
    )
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

    @field_validator(
        "database_url",
        "default_api_key",
        "default_runtime_key",
        "default_project_name",
        mode="before",
    )
    @classmethod
    def blank_string_uses_default(cls, value: Any, info):
        if not isinstance(value, str) or value.strip():
            return value
        defaults = {
            "database_url": DEFAULT_DATABASE_URL,
            "default_api_key": DEFAULT_API_KEY,
            "default_runtime_key": DEFAULT_RUNTIME_KEY,
            "default_project_name": DEFAULT_PROJECT_NAME,
        }
        return defaults[info.field_name]

    @field_validator("secret_backend")
    @classmethod
    def valid_secret_backend(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"memory", "aws", "vault", "openbao"}:
            raise ValueError(
                "LOGLLAMA_SECRET_BACKEND must be 'memory', 'aws', 'vault', or 'openbao'."
            )
        return normalized


settings = Settings()
