from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Infrastructure settings loaded from environment variables."""

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    app_base_url: str = Field(default="http://localhost:8080", validation_alias="APP_BASE_URL")
    app_port: int = Field(default=8080, validation_alias="APP_PORT")
    app_secret_key: str = Field(default="dev-secret-change-me", validation_alias="APP_SECRET_KEY")

    database_url: str = Field(
        default="postgresql+psycopg://invoice_app:change-me@postgres:5432/invoice_app",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://redis:6379/0", validation_alias="REDIS_URL")

    storage_path: Path = Field(default=Path("/data/uploads"), validation_alias="STORAGE_PATH")
    export_path: Path = Field(default=Path("/data/exports"), validation_alias="EXPORT_PATH")
    tmp_path: Path = Field(default=Path("/data/tmp"), validation_alias="TMP_PATH")

    ocr_config_encryption_key: str = Field(
        default="dev-ocr-config-encryption-key-change-me",
        validation_alias="OCR_CONFIG_ENCRYPTION_KEY",
    )
    worker_concurrency: int = Field(default=4, validation_alias="WORKER_CONCURRENCY")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

