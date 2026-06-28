from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LLM Fine-Tuner API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://llm_finetuner:llm_finetuner_password@localhost:5432/llm_finetuner"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = Field(default="change-me-in-development-use-at-least-32-bytes", min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    api_cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @computed_field
    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
