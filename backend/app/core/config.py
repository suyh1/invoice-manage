import base64
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from cryptography.fernet import Fernet, InvalidToken
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


SENSITIVE_KEY_PARTS = (
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
)


@dataclass(frozen=True)
class OcrProviderDefaults:
    provider: str
    endpoint: str
    region: str
    action: str
    api_version: str
    qps_limit: int
    quota_warning_percent: int
    quota_warning_remaining: int


@dataclass(frozen=True)
class UploadValidationDefaults:
    allowed_extensions: tuple[str, ...]
    max_base64_size_bytes: int
    min_image_dimension_px: int
    max_image_dimension_px: int
    max_pdf_pages: int


@dataclass(frozen=True)
class OcrRetryDefaults:
    max_attempts: int
    backoff_seconds: tuple[int, ...]


TENCENT_OCR_DEFAULTS = OcrProviderDefaults(
    provider="tencent",
    endpoint="ocr.tencentcloudapi.com",
    region="ap-guangzhou",
    action="VatInvoiceOCR",
    api_version="2018-11-19",
    qps_limit=8,
    quota_warning_percent=80,
    quota_warning_remaining=100,
)

UPLOAD_VALIDATION_DEFAULTS = UploadValidationDefaults(
    allowed_extensions=("png", "jpg", "jpeg", "pdf"),
    max_base64_size_bytes=10 * 1024 * 1024,
    min_image_dimension_px=20,
    max_image_dimension_px=10000,
    max_pdf_pages=1,
)

OCR_RETRY_DEFAULTS = OcrRetryDefaults(max_attempts=3, backoff_seconds=(10, 30, 120))


class Settings(BaseSettings):
    """Infrastructure settings loaded from environment variables."""

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    app_base_url: str = Field(default="http://localhost:8080", validation_alias="APP_BASE_URL")
    app_port: int = Field(default=8080, validation_alias="APP_PORT")
    app_secret_key: str = Field(default="dev-secret-change-me", validation_alias="APP_SECRET_KEY")
    session_cookie_secure: bool = Field(default=False, validation_alias="SESSION_COOKIE_SECURE")
    session_cookie_samesite: str = Field(default="Lax", validation_alias="SESSION_COOKIE_SAMESITE")

    database_url_override: str | None = Field(default=None, validation_alias="DATABASE_URL")
    postgres_host: str = Field(default="postgres", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_db: str = Field(default="invoice_app", validation_alias="POSTGRES_DB")
    postgres_user: str = Field(default="invoice_app", validation_alias="POSTGRES_USER")
    postgres_password: str = Field(default="change-me", validation_alias="POSTGRES_PASSWORD")
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

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)

    def safe_dict(self) -> dict[str, Any]:
        """Return settings that can be exposed in diagnostics without secrets."""

        return {
            "app_env": self.app_env,
            "app_base_url": self.app_base_url,
            "app_port": self.app_port,
            "session_cookie_secure": self.session_cookie_secure,
            "session_cookie_samesite": self.session_cookie_samesite,
            "database_url": redact_url_password(self.database_url),
            "redis_url": redact_url_password(self.redis_url),
            "storage_path": str(self.storage_path),
            "export_path": str(self.export_path),
            "tmp_path": str(self.tmp_path),
            "worker_concurrency": self.worker_concurrency,
        }


class CredentialCipher:
    """Encrypt and decrypt OCR provider credential payloads for database storage."""

    algorithm = "fernet-sha256"

    def __init__(self, encryption_key: str) -> None:
        if not encryption_key or len(encryption_key.encode("utf-8")) < 32:
            raise ValueError("OCR_CONFIG_ENCRYPTION_KEY must be at least 32 bytes")
        digest = hashlib.sha256(encryption_key.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt_payload(self, payload: dict[str, Any]) -> dict[str, str]:
        plaintext = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {"alg": self.algorithm, "ciphertext": self._fernet.encrypt(plaintext).decode("ascii")}

    def decrypt_payload(self, encrypted_payload: dict[str, str]) -> dict[str, Any]:
        if encrypted_payload.get("alg") != self.algorithm:
            raise ValueError("Unsupported credential encryption algorithm")
        try:
            plaintext = self._fernet.decrypt(encrypted_payload["ciphertext"].encode("ascii"))
        except (InvalidToken, KeyError) as exc:
            raise ValueError("Credential payload cannot be decrypted") from exc
        decoded = json.loads(plaintext.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("Credential payload must decode to an object")
        return decoded


def redact_url_password(value: str) -> str:
    parsed = urlsplit(value)
    if not parsed.password:
        return value
    username = parsed.username or ""
    hostname = parsed.hostname or ""
    auth = f"{username}:***@" if username else "***@"
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{auth}{hostname}{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def redact_secrets(value: Any, extra_secrets: list[str] | tuple[str, ...] | None = None) -> Any:
    if isinstance(value, dict):
        return {
            key: mask_sensitive_value(item) if is_sensitive_key(str(key)) else redact_secrets(item, extra_secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item, extra_secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item, extra_secrets) for item in value)
    if isinstance(value, str):
        redacted = value
        for secret in extra_secrets or ():
            if secret:
                redacted = redacted.replace(secret, "***")
        return redacted
    return value


def is_sensitive_key(key: str) -> bool:
    normalized = key.replace("-", "_").lower()
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def mask_sensitive_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: mask_sensitive_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [mask_sensitive_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(mask_sensitive_value(item) for item in value)
    return "***"


@lru_cache
def get_settings() -> Settings:
    return Settings()
