from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.domain.ocr.models import OcrProviderConfig
from app.domain.ocr.quota import quota_snapshot
from app.domain.user.models import User


router = APIRouter(prefix="/api/v1/ocr-quota", tags=["ocr-quota"])


@router.get("/status")
def get_ocr_quota_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, Any]]:
    del current_user
    provider_config = db.scalar(
        select(OcrProviderConfig).where(
            OcrProviderConfig.enabled.is_(True),
            OcrProviderConfig.is_default.is_(True),
        )
    )
    if provider_config is None:
        return {
            "data": {
                "quota_total": None,
                "quota_used": None,
                "used_percent": None,
                "level": "none",
            }
        }

    snapshot = quota_snapshot(provider_config)
    return {
        "data": {
            "quota_total": snapshot["free_quota_total"],
            "quota_used": snapshot["free_quota_used"],
            "used_percent": snapshot["used_percent"],
            "level": snapshot["alert_level"],
        }
    }
