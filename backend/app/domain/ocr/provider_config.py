from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import CredentialCipher, get_settings
from app.core.errors import AppError
from app.domain.ocr.models import OcrProviderConfig, OcrQuotaAlert, QuotaSource
from app.domain.ocr.quota import quota_snapshot, sync_quota_alerts


SUPPORTED_PROVIDERS = {"tencent", "mock", "aliyun"}


class OcrProviderConfigService:
    def __init__(self) -> None:
        self._cipher = CredentialCipher(get_settings().ocr_config_encryption_key)

    def list_configs(self, db: Session) -> list[dict[str, Any]]:
        configs = list(db.scalars(select(OcrProviderConfig).order_by(OcrProviderConfig.created_at, OcrProviderConfig.display_name)))
        return [self.serialize_config(config) for config in configs]

    def get_config(self, db: Session, provider_config_id) -> OcrProviderConfig:
        config = db.get(OcrProviderConfig, provider_config_id)
        if config is None:
            raise AppError("OCR_PROVIDER_CONFIG_MISSING", "OCR provider configuration was not found", status_code=404)
        return config

    def create_config(self, db: Session, payload: dict[str, Any], *, actor) -> OcrProviderConfig:
        provider = self._validate_provider(payload["provider"])
        should_be_default = bool(payload.get("is_default", False))
        config = OcrProviderConfig(
            provider=provider,
            display_name=payload["display_name"],
            enabled=bool(payload.get("enabled", False)),
            is_default=False,
            endpoint=payload.get("endpoint") or self._default_value(provider, "endpoint"),
            region=payload.get("region") or self._default_value(provider, "region"),
            action=payload.get("action") or self._default_value(provider, "action"),
            api_version=payload.get("api_version") or self._default_value(provider, "api_version"),
            qps_limit=int(payload.get("qps_limit") or self._default_value(provider, "qps_limit")),
            quota_source=QuotaSource((payload.get("quota") or {}).get("source", "manual")),
            free_quota_total=(payload.get("quota") or {}).get("free_quota_total"),
            free_quota_used=(payload.get("quota") or {}).get("free_quota_used"),
            quota_warning_percent=int((payload.get("quota") or {}).get("quota_warning_percent", 80)),
            quota_warning_remaining=int((payload.get("quota") or {}).get("quota_warning_remaining", 100)),
            quota_reset_at=self._parse_datetime((payload.get("quota") or {}).get("quota_reset_at")),
            created_by=actor.id,
            updated_by=actor.id,
        )
        if payload.get("credential"):
            self._apply_credential(config, payload["credential"])
        db.add(config)
        db.flush()
        if should_be_default:
            self.set_default(db, config, actor=actor)
        sync_quota_alerts(db, config)
        db.flush()
        return config

    def update_config(self, db: Session, config: OcrProviderConfig, payload: dict[str, Any], *, actor) -> OcrProviderConfig:
        for field in ("display_name", "endpoint", "region", "action", "api_version"):
            if field in payload:
                setattr(config, field, payload[field])
        if "enabled" in payload:
            config.enabled = bool(payload["enabled"])
        if "qps_limit" in payload:
            config.qps_limit = int(payload["qps_limit"])
        if "credential" in payload and payload["credential"]:
            self._apply_credential(config, payload["credential"])
        if "quota" in payload:
            quota = payload["quota"]
            if "source" in quota:
                config.quota_source = QuotaSource(quota["source"])
            for field in ("free_quota_total", "free_quota_used", "quota_warning_percent", "quota_warning_remaining"):
                if field in quota:
                    setattr(config, field, quota[field])
            if "quota_reset_at" in quota:
                config.quota_reset_at = self._parse_datetime(quota["quota_reset_at"])
        config.updated_by = actor.id
        if payload.get("is_default") is True:
            self.set_default(db, config, actor=actor)
        sync_quota_alerts(db, config)
        db.flush()
        return config

    def rotate_credentials(self, db: Session, config: OcrProviderConfig, *, credential: dict[str, str], actor) -> OcrProviderConfig:
        self._apply_credential(config, credential)
        config.updated_by = actor.id
        db.flush()
        return config

    def set_default(self, db: Session, config: OcrProviderConfig, *, actor) -> OcrProviderConfig:
        existing_defaults = list(
            db.scalars(select(OcrProviderConfig).where(OcrProviderConfig.id != config.id, OcrProviderConfig.is_default.is_(True)))
        )
        for other in existing_defaults:
            other.is_default = False
            other.updated_by = actor.id
        if existing_defaults:
            db.flush()
        config.enabled = True
        config.is_default = True
        config.updated_by = actor.id
        db.flush()
        return config

    def calibrate_quota(self, db: Session, config: OcrProviderConfig, payload: dict[str, Any], *, actor) -> OcrProviderConfig:
        config.free_quota_total = payload.get("free_quota_total")
        config.free_quota_used = payload.get("free_quota_used")
        config.quota_reset_at = self._parse_datetime(payload.get("quota_reset_at"))
        config.updated_by = actor.id
        sync_quota_alerts(db, config)
        db.flush()
        return config

    def decrypt_credential(self, config: OcrProviderConfig) -> dict[str, str] | None:
        if not config.credential_ciphertext:
            return None
        return self._cipher.decrypt_payload(config.credential_ciphertext)

    def serialize_config(self, config: OcrProviderConfig) -> dict[str, Any]:
        return {
            "id": str(config.id),
            "provider": config.provider,
            "display_name": config.display_name,
            "enabled": config.enabled,
            "is_default": config.is_default,
            "configured": config.credential_ciphertext is not None,
            "credential_fingerprint": config.credential_fingerprint,
            "endpoint": config.endpoint,
            "region": config.region,
            "action": config.action,
            "api_version": config.api_version,
            "qps_limit": config.qps_limit,
            "last_test_status": config.last_test_status,
            "last_tested_at": config.last_tested_at.isoformat() if config.last_tested_at else None,
            "quota": quota_snapshot(config),
        }

    def serialize_alert(self, alert: OcrQuotaAlert) -> dict[str, Any]:
        return {
            "id": str(alert.id),
            "provider_config_id": str(alert.provider_config_id),
            "level": alert.level.value,
            "status": alert.status.value,
            "message": alert.message,
            "quota_total": alert.quota_total,
            "quota_used": alert.quota_used,
            "quota_remaining": alert.quota_remaining,
            "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
            "acknowledged_by": str(alert.acknowledged_by) if alert.acknowledged_by else None,
        }

    def _apply_credential(self, config: OcrProviderConfig, credential: dict[str, str]) -> None:
        config.credential_ciphertext = self._cipher.encrypt_payload(credential)
        config.credential_fingerprint = fingerprint_credential(credential)

    def _validate_provider(self, provider: str) -> str:
        if provider not in SUPPORTED_PROVIDERS:
            raise AppError("OCR_PROVIDER_CONFIG_MISSING", f"Unsupported OCR provider: {provider}", status_code=400)
        return provider

    def _default_value(self, provider: str, field: str):
        defaults = {
            "tencent": {
                "endpoint": "ocr.tencentcloudapi.com",
                "region": "ap-guangzhou",
                "action": "VatInvoiceOCR",
                "api_version": "2018-11-19",
                "qps_limit": 8,
            },
            "mock": {
                "endpoint": "mock",
                "region": "local",
                "action": "VatInvoiceOCR",
                "api_version": "mock-1",
                "qps_limit": 100,
            },
            "aliyun": {
                "endpoint": "ocr-api.aliyun.com",
                "region": "cn-hangzhou",
                "action": "Unsupported",
                "api_version": "v1",
                "qps_limit": 8,
            },
        }
        return defaults[provider][field]

    def _parse_datetime(self, value: str | None):
        if not value:
            return None
        return datetime.fromisoformat(value)


def fingerprint_credential(credential: dict[str, str]) -> str:
    payload = json.dumps(credential, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()[:12]}"
