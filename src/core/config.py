"""
Configuration module for KRYVARACODE AI System Stack.

All settings are read from environment variables or a local ``.env`` file
(pydantic-settings). Never hard-code secrets here - defaults are for local
development only.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Settings
    APP_NAME: str = "KRYVARACODE"
    APP_ENV: str = Field(default="development", validation_alias="APP_ENV")
    APP_DEBUG: bool = Field(default=False, validation_alias="APP_DEBUG")
    PROJECT_VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS Settings
    BACKEND_CORS_ORIGINS: list[str] = []

    # Database Settings
    DATABASE_URL: str = Field(validation_alias="DATABASE_URL")

    # Redis Settings
    REDIS_URL: str = Field(validation_alias="REDIS_URL")

    # MLflow Settings
    MLFLOW_TRACKING_URI: str = Field(validation_alias="MLFLOW_TRACKING_URI")
    MLFLOW_S3_ENDPOINT_URL: str = Field(validation_alias="MLFLOW_S3_ENDPOINT_URL")
    AWS_ACCESS_KEY_ID: str = Field(validation_alias="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: str = Field(validation_alias="AWS_SECRET_ACCESS_KEY")

    # Model Settings
    MODEL_NAME: str = Field(default="kryvara_model", validation_alias="MODEL_NAME")

    # Security Settings
    SECRET_KEY: str = Field(validation_alias="SECRET_KEY")
    JWT_SECRET_KEY: str = Field(default="", validation_alias="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = "RS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30 minutes (was 8 days)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    RSA_PRIVATE_KEY_PATH: Path = Field(
        default=Path("src/core/keys/private.pem"),
        validation_alias="RSA_PRIVATE_KEY_PATH",
    )
    RSA_PUBLIC_KEY_PATH: Path = Field(
        default=Path("src/core/keys/public.pem"),
        validation_alias="RSA_PUBLIC_KEY_PATH",
    )

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_STRATEGY: str = "fixed-window"  # fixed-window or sliding-window

    # Object Storage Settings
    MINIO_ENDPOINT: str = Field(validation_alias="MINIO_ENDPOINT")
    MINIO_ACCESS_KEY: str = Field(validation_alias="MINIO_ACCESS_KEY")
    MINIO_SECRET_KEY: str = Field(validation_alias="MINIO_SECRET_KEY")
    MINIO_BUCKET_MODELS: str = Field(default="kryvara-models", validation_alias="MINIO_BUCKET_MODELS")
    MINIO_BUCKET_DATA: str = Field(default="kryvara-data", validation_alias="MINIO_BUCKET_DATA")

    # PostgreSQL (for MLflow backend store)
    POSTGRES_USER: str = Field(validation_alias="POSTGRES_USER")
    POSTGRES_PASSWORD: str = Field(validation_alias="POSTGRES_PASSWORD")
    POSTGRES_DB: str = Field(validation_alias="POSTGRES_DB")

    # Logging / Monitoring Settings
    LOG_LEVEL: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    PROMETHEUS_PORT: int = 9090
    GRAFANA_PORT: int = 3000
    JAEGER_PORT: int = Field(default=16686, validation_alias="JAEGER_PORT")
    GRAFANA_ADMIN_USER: str = Field(default="admin", validation_alias="GRAFANA_ADMIN_USER")
    GRAFANA_ADMIN_PASSWORD: str = Field(validation_alias="GRAFANA_ADMIN_PASSWORD")

    # External API Keys
    OPENAI_API_KEY: str = Field(validation_alias="OPENAI_API_KEY")
    HUGGINGFACE_API_KEY: str = Field(validation_alias="HUGGINGFACE_API_KEY")

    # Data Settings
    DATA_DIR: str = "data"

    # Qdrant Vector Database Settings
    QDRANT_URL: str = Field(default="http://localhost:6333", validation_alias="QDRANT_URL")
    QDRANT_API_KEY: str | None = Field(default=None, validation_alias="QDRANT_API_KEY")
    QDRANT_COLLECTION_NAME: str = Field(default="kryvara_rag", validation_alias="QDRANT_COLLECTION_NAME")
    QDRANT_VECTOR_SIZE: int = Field(default=384, validation_alias="QDRANT_VECTOR_SIZE")
    QDRANT_HNSW_M: int = Field(default=16, validation_alias="QDRANT_HNSW_M")
    QDRANT_HNSW_EF_CONSTRUCT: int = Field(default=100, validation_alias="QDRANT_HNSW_EF_CONSTRUCT")
    QDRANT_ENABLE_HYBRID: bool = Field(default=True, validation_alias="QDRANT_ENABLE_HYBRID")
    QDRANT_SPARSE_VECTOR_NAME: str = Field(default="bm25", validation_alias="QDRANT_SPARSE_VECTOR_NAME")
    QDRANT_DENSE_VECTOR_NAME: str = Field(default="dense", validation_alias="QDRANT_DENSE_VECTOR_NAME")

    # E2B Sandbox Settings
    E2B_API_KEY: str | None = Field(default=None, validation_alias="E2B_API_KEY")
    E2B_TEMPLATE_ID: str = Field(default="base", validation_alias="E2B_TEMPLATE_ID")
    E2B_TIMEOUT_SECONDS: int = Field(default=60, validation_alias="E2B_TIMEOUT_SECONDS")
    E2B_ENABLED: bool = Field(default=False, validation_alias="E2B_ENABLED")
    E2B_CPU_LIMIT: float = Field(default=1.0, validation_alias="E2B_CPU_LIMIT")
    E2B_MEMORY_LIMIT_MB: int = Field(default=512, validation_alias="E2B_MEMORY_LIMIT_MB")

    # Langfuse LLM Observability Settings
    LANGFUSE_PUBLIC_KEY: str | None = Field(default=None, validation_alias="LANGFUSE_PUBLIC_KEY")
    LANGFUSE_SECRET_KEY: str | None = Field(default=None, validation_alias="LANGFUSE_SECRET_KEY")
    LANGFUSE_HOST: str = Field(default="https://cloud.langfuse.com", validation_alias="LANGFUSE_HOST")
    LANGFUSE_ENABLED: bool = Field(default=False, validation_alias="LANGFUSE_ENABLED")
    LANGFUSE_FLUSH_INTERVAL: int = Field(default=10, validation_alias="LANGFUSE_FLUSH_INTERVAL")
    LANGFUSE_DEBUG: bool = Field(default=False, validation_alias="LANGFUSE_DEBUG")

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", env_file_encoding="utf-8")

    @field_validator("RSA_PRIVATE_KEY_PATH", "RSA_PUBLIC_KEY_PATH", mode="before")
    @classmethod
    def _resolve_path(cls, v: str | Path) -> Path:
        return Path(v)

    @property
    def jwt_secret(self) -> str:
        """JWT signing key. Falls back to SECRET_KEY for backwards
        compatibility with deployments that only set SECRET_KEY."""
        return self.JWT_SECRET_KEY or self.SECRET_KEY

    @property
    def rsa_private_key(self) -> str:
        return self.RSA_PRIVATE_KEY_PATH.read_text()

    @property
    def rsa_public_key(self) -> str:
        return self.RSA_PUBLIC_KEY_PATH.read_text()

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cache a single Settings instance per process."""
    return Settings()


# Convenience global instance (kept for backwards compatibility with
# existing modules that do ``from src.core.config import settings``).
settings = get_settings()
