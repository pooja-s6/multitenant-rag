from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-change-me"
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration. Values come from the environment or a root `.env` file."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Multi-Tenant RAG"
    environment: str = "development"

    database_url: str = "postgresql+psycopg://rag:rag@localhost:5432/rag"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    small_model: str = "gpt-4o-mini"
    large_model: str = "gpt-4o"

    cache_similarity_threshold: float = 0.92
    cache_ttl: int = 3600

    retrieval_top_k: int = 5
    retrieval_similarity_threshold: float = 0.30
    routing_complexity_threshold: float = 0.45

    small_model_price: float = 0.15
    large_model_price: float = 2.50
    small_model_output_price: float = 0.60
    large_model_output_price: float = 10.00

    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    @field_validator(
        "cache_similarity_threshold",
        "retrieval_similarity_threshold",
        "routing_complexity_threshold",
    )
    @classmethod
    def threshold_in_unit_interval(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        return value

    @field_validator("embedding_dimension", "retrieval_top_k", "cache_ttl", "access_token_expire_minutes")
    @classmethod
    def positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be positive")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def uses_dev_jwt_secret(self) -> bool:
        return self.jwt_secret == DEV_JWT_SECRET


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.environment.lower() == "production" and settings.uses_dev_jwt_secret:
        raise RuntimeError("JWT_SECRET must be changed when ENVIRONMENT is production")
    return settings
