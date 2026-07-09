from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.domain.ocr.models import OcrQuotaAlert, QuotaAlertStatus
from app.domain.ocr.provider_config import OcrProviderConfigService
from app.domain.ocr.quota import acknowledge_alert
from app.domain.ocr.registry import get_registry
from app.domain.user.models import User, UserRole


router = APIRouter(prefix="/api/v1/admin", tags=["admin-ocr"])


class ProviderPayload(BaseModel):
    provider: str
    display_name: str
    enabled: bool = False
    is_default: bool = False
    credential: dict[str, str] | None = None
    region: str | None = None
    endpoint: str | None = None
    action: str | None = None
    api_version: str | None = None
    qps_limit: int | None = None
    quota: dict[str, Any] | None = None


class ProviderPatchPayload(BaseModel):
    display_name: str | None = None
    enabled: bool | None = None
    is_default: bool | None = None
    credential: dict[str, str] | None = None
    region: str | None = None
    endpoint: str | None = None
    action: str | None = None
    api_version: str | None = None
    qps_limit: int | None = None
    quota: dict[str, Any] | None = None


class RotateCredentialPayload(BaseModel):
    secret_id: str
    secret_key: str


class QuotaCalibrationPayload(BaseModel):
    free_quota_total: int | None = None
    free_quota_used: int | None = None
    quota_reset_at: str | None = None
    note: str | None = None


@router.get("/ocr-providers")
def list_ocr_providers(
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, list[dict[str, Any]]]:
    del current_user
    service = OcrProviderConfigService()
    return {"data": service.list_configs(db)}


@router.post("/ocr-providers")
def create_ocr_provider(
    payload: ProviderPayload,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, Any]]:
    service = OcrProviderConfigService()
    config = service.create_config(db, payload.model_dump(exclude_none=True), actor=current_user)
    db.commit()
    db.refresh(config)
    return {"data": service.serialize_config(config)}


@router.get("/ocr-providers/{provider_config_id}")
def get_ocr_provider(
    provider_config_id: UUID,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, Any]]:
    del current_user
    service = OcrProviderConfigService()
    config = service.get_config(db, provider_config_id)
    return {"data": service.serialize_config(config)}


@router.patch("/ocr-providers/{provider_config_id}")
def update_ocr_provider(
    provider_config_id: UUID,
    payload: ProviderPatchPayload,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, Any]]:
    service = OcrProviderConfigService()
    config = service.get_config(db, provider_config_id)
    updated = service.update_config(db, config, payload.model_dump(exclude_none=True), actor=current_user)
    db.commit()
    db.refresh(updated)
    return {"data": service.serialize_config(updated)}


@router.post("/ocr-providers/{provider_config_id}/test")
def test_ocr_provider(
    provider_config_id: UUID,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, Any]]:
    service = OcrProviderConfigService()
    config = service.get_config(db, provider_config_id)
    result = get_registry().get_client(config.provider).test_connection(config, service.decrypt_credential(config))
    config.last_test_status = "success" if result.get("ok") else "failed"
    from datetime import UTC, datetime

    config.last_tested_at = datetime.now(UTC)
    config.updated_by = current_user.id
    db.commit()
    return {"data": {"status": config.last_test_status, "message": result.get("message", "")}}


@router.post("/ocr-providers/{provider_config_id}/set-default")
def set_default_ocr_provider(
    provider_config_id: UUID,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, Any]]:
    service = OcrProviderConfigService()
    config = service.get_config(db, provider_config_id)
    service.set_default(db, config, actor=current_user)
    db.commit()
    db.refresh(config)
    return {"data": service.serialize_config(config)}


@router.post("/ocr-providers/{provider_config_id}/rotate-credential")
def rotate_ocr_provider_credential(
    provider_config_id: UUID,
    payload: RotateCredentialPayload,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, Any]]:
    service = OcrProviderConfigService()
    config = service.get_config(db, provider_config_id)
    updated = service.rotate_credentials(
        db,
        config,
        credential=payload.model_dump(),
        actor=current_user,
    )
    db.commit()
    db.refresh(updated)
    return {"data": service.serialize_config(updated)}


@router.post("/ocr-providers/{provider_config_id}/quota-calibration")
def calibrate_ocr_provider_quota(
    provider_config_id: UUID,
    payload: QuotaCalibrationPayload,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, Any]]:
    service = OcrProviderConfigService()
    config = service.get_config(db, provider_config_id)
    updated = service.calibrate_quota(db, config, payload.model_dump(exclude_none=True), actor=current_user)
    db.commit()
    db.refresh(updated)
    return {"data": service.serialize_config(updated)}


@router.get("/ocr-quota-alerts")
def list_ocr_quota_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, list[dict[str, Any]]]:
    if current_user.role not in {UserRole.admin, UserRole.finance}:
        from app.core.errors import AppError

        raise AppError("AUTH_FORBIDDEN", "You do not have permission to access this resource", status_code=403)
    service = OcrProviderConfigService()
    alerts = list(
        db.scalars(select(OcrQuotaAlert).where(OcrQuotaAlert.status.in_([QuotaAlertStatus.active, QuotaAlertStatus.acknowledged])))
    )
    return {"data": [service.serialize_alert(alert) for alert in alerts]}


@router.post("/ocr-quota-alerts/{alert_id}/acknowledge")
def acknowledge_ocr_quota_alert(
    alert_id: UUID,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, Any]]:
    service = OcrProviderConfigService()
    alert = db.get(OcrQuotaAlert, alert_id)
    acknowledged = acknowledge_alert(alert, current_user)
    db.commit()
    return {"data": service.serialize_alert(acknowledged)}
