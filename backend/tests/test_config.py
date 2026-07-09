import json

from app.core.config import (
    CredentialCipher,
    Settings,
    TENCENT_OCR_DEFAULTS,
    redact_secrets,
)


def test_settings_do_not_load_tencent_cloud_credentials_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("TENCENT_SECRET_ID", "AKID_FROM_ENV")
    monkeypatch.setenv("TENCENT_SECRET_KEY", "SECRET_FROM_ENV")
    monkeypatch.setenv("TENCENTCLOUD_SECRETID", "AKID_LEGACY_ENV")
    monkeypatch.setenv("TENCENTCLOUD_SECRETKEY", "SECRET_LEGACY_ENV")

    settings = Settings(_env_file=None)
    serialized = json.dumps(settings.safe_dict(), ensure_ascii=False)

    assert "AKID_FROM_ENV" not in serialized
    assert "SECRET_FROM_ENV" not in serialized
    assert "AKID_LEGACY_ENV" not in serialized
    assert "SECRET_LEGACY_ENV" not in serialized
    assert not any("tencent" in field.lower() and "secret" in field.lower() for field in Settings.model_fields)


def test_safe_settings_dump_excludes_application_secrets() -> None:
    settings = Settings(
        _env_file=None,
        APP_SECRET_KEY="super-secret-app-key",
        OCR_CONFIG_ENCRYPTION_KEY="super-secret-ocr-key",
        DATABASE_URL="postgresql+psycopg://invoice:pass@postgres:5432/app",
    )

    safe_dump = settings.safe_dict()
    serialized = json.dumps(safe_dump, ensure_ascii=False)

    assert "super-secret-app-key" not in serialized
    assert "super-secret-ocr-key" not in serialized
    assert "pass@postgres" not in serialized
    assert safe_dump["database_url"] == "postgresql+psycopg://invoice:***@postgres:5432/app"


def test_credential_cipher_encrypts_and_decrypts_payload_without_plaintext() -> None:
    cipher = CredentialCipher("unit-test-encryption-key-with-enough-entropy")
    credential = {"secret_id": "AKIDEXAMPLE", "secret_key": "very-sensitive-key"}

    encrypted = cipher.encrypt_payload(credential)
    serialized = json.dumps(encrypted, ensure_ascii=False)

    assert encrypted["alg"] == "fernet-sha256"
    assert "AKIDEXAMPLE" not in serialized
    assert "very-sensitive-key" not in serialized
    assert cipher.decrypt_payload(encrypted) == credential


def test_redact_secrets_handles_nested_log_payloads() -> None:
    payload = {
        "provider": "tencent",
        "credential": {"secret_id": "AKIDEXAMPLE", "secret_key": "very-sensitive-key"},
        "headers": {"Authorization": "Bearer token-value"},
        "message": "failed with very-sensitive-key for AKIDEXAMPLE",
    }

    redacted = redact_secrets(payload, extra_secrets=["AKIDEXAMPLE", "very-sensitive-key"])
    serialized = json.dumps(redacted, ensure_ascii=False)

    assert "AKIDEXAMPLE" not in serialized
    assert "very-sensitive-key" not in serialized
    assert redacted["credential"]["secret_id"] == "***"
    assert redacted["credential"]["secret_key"] == "***"
    assert redacted["headers"]["Authorization"] == "***"


def test_ocr_defaults_are_code_defaults_not_settings_fields() -> None:
    settings = Settings(_env_file=None, TENCENT_OCR_QPS_LIMIT="99")

    assert TENCENT_OCR_DEFAULTS.provider == "tencent"
    assert TENCENT_OCR_DEFAULTS.endpoint == "ocr.tencentcloudapi.com"
    assert TENCENT_OCR_DEFAULTS.action == "VatInvoiceOCR"
    assert TENCENT_OCR_DEFAULTS.api_version == "2018-11-19"
    assert TENCENT_OCR_DEFAULTS.qps_limit == 8
    assert "tencent_ocr_qps_limit" not in Settings.model_fields
