from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db


router = APIRouter(tags=["health"])


def get_redis_client():
    import redis

    return redis.Redis.from_url(get_settings().redis_url)


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(db: Session = Depends(get_db), redis_client: Any = Depends(get_redis_client)) -> dict[str, Any]:
    checks: dict[str, str] = {}
    try:
        db.execute(text("select 1"))
        checks["database"] = "ok"
    except Exception as exc:
        raise AppError("SERVICE_NOT_READY", "Service dependencies are not ready", status_code=503, retryable=True) from exc

    try:
        if redis_client.ping() is not True:
            raise RuntimeError("redis ping failed")
        checks["redis"] = "ok"
    except Exception as exc:
        raise AppError("SERVICE_NOT_READY", "Service dependencies are not ready", status_code=503, retryable=True) from exc

    return {"status": "ready", "checks": checks}
