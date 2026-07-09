from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(
        default="postgresql+asyncpg://logllama:logllama@localhost:5432/logllama",
        validation_alias="DATABASE_URL",
    )
    default_api_key: str = Field(default="llama-dev-key", validation_alias="LOGLLAMA_DEFAULT_API_KEY")
    default_project_name: str = Field(default="Development", validation_alias="LOGLLAMA_DEFAULT_PROJECT_NAME")
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
