from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LLM Fine-Tuner API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://llm_finetuner:llm_finetuner_password@localhost:5432/llm_finetuner"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    storage_path: str = "storage"
    gpu_agent_token: str | None = None
    celery_training_max_retries: int = 3
    jwt_secret_key: str = Field(default="change-me-in-development-use-at-least-32-bytes", min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    api_cors_origins: str = "http://localhost:3000"
    llm_semantic_mapping_url: str | None = None
    llm_semantic_mapping_api_key: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1"
    dataset_search_limit: int = 10
    dataset_preview_rows: int = 10
    mapping_cache_ttl_seconds: int = 86400
    gpu_provider: str = "runpod"
    runpod_api_key: str | None = None
    runpod_template_id: str | None = None
    runpod_default_gpu: str = "A100"
    runpod_volume_size: int = 100
    runpod_container_disk: int = 50
    runpod_region: str | None = None
    runpod_agent_port: int = 8001
    gpu_create_timeout_seconds: int = 900
    gpu_operation_max_retries: int = 3
    training_worker_poll_interval_seconds: float = 10.0
    training_worker_poll_timeout_seconds: int = 86400

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @computed_field
    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]

    @computed_field
    @property
    def resolved_celery_broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @computed_field
    @property
    def resolved_celery_result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
