"""
Configuration module for KRYVARACODE AI System Stack.

All settings are read from environment variables or a local ``.env`` file
(pydantic-settings). Never hard-code secrets here - defaults are for local
development only.
"""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Settings
    APP_NAME: str = "KRYVARACODE"
    APP_ENV: str = Field(default="development", validation_alias="APP_ENV")
    APP_DEBUG: bool = Field(default=True, validation_alias="APP_DEBUG")
    PROJECT_VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS Settings
    BACKEND_CORS_ORIGINS: List[str] = []

    # Database Settings
    DATABASE_URL: str = Field(
        default="postgresql://user:password@localhost:5432/kryvaracode",
        validation_alias="DATABASE_URL",
    )

    # Redis Settings
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0", validation_alias="REDIS_URL"
    )

    # MLflow Settings
    MLFLOW_TRACKING_URI: str = Field(
        default="http://localhost:5000", validation_alias="MLFLOW_TRACKING_URI"
    )

    # Model Settings
    MODEL_NAME: str = Field(default="kryvara_model", validation_alias="MODEL_NAME")

    # Security Settings
    SECRET_KEY: str = Field(
        default="your-secret-key-here", validation_alias="SECRET_KEY"
    )
    JWT_SECRET_KEY: str = Field(
        default="your-jwt-secret-key-here", validation_alias="JWT_SECRET_KEY"
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # Rate Limiting (structural placeholder - enforcement injected later)
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_DEFAULT: str = "100/minute"

    # Object Storage Settings
    MINIO_ENDPOINT: str = Field(
        default="localhost:9000", validation_alias="MINIO_ENDPOINT"
    )
    MINIO_ACCESS_KEY: str = Field(
        default="minioadmin", validation_alias="MINIO_ACCESS_KEY"
    )
    MINIO_SECRET_KEY: str = Field(
        default="minioadmin", validation_alias="MINIO_SECRET_KEY"
    )
    MINIO_BUCKET_MODELS: str = Field(
        default="kryvara-models", validation_alias="MINIO_BUCKET_MODELS"
    )
    MINIO_BUCKET_DATA: str = Field(
        default="kryvara-data", validation_alias="MINIO_BUCKET_DATA"
    )

    # Logging / Monitoring Settings
    LOG_LEVEL: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    PROMETHEUS_PORT: int = 9090
    GRAFANA_PORT: int = 3000

    # Data Settings
    DATA_DIR: str = "data"

    model_config = SettingsConfigDict(
        case_sensitive=True, env_file=".env", env_file_encoding="utf-8"
    )

    @property
    def jwt_secret(self) -> str:
        """JWT signing key. Falls back to SECRET_KEY for backwards
        compatibility with deployments that only set SECRET_KEY."""
        return self.JWT_SECRET_KEY or self.SECRET_KEY

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cache a single Settings instance per process."""
    return Settings()


# Convenience global instance (kept for backwards compatibility with
# existing modules that do ``from src.core.config import settings``).
settings = get_settings()
