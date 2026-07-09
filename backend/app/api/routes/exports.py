from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.domain.export.service import ExportService, serialize_export_task
from app.domain.user.models import User


router = APIRouter(prefix="/api/v1/exports", tags=["exports"])


class ExportCreatePayload(BaseModel):
    format: str
    scope: str = "filtered_invoices"
    filters: dict[str, Any] | None = None
    include_items: bool = True
    include_ocr_meta: bool = True


@router.post("")
def create_export(
    payload: ExportCreatePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    task = ExportService().create_task(db, payload.model_dump(), current_user)
    db.commit()
    db.refresh(task)
    return {"data": serialize_export_task(task)}


@router.get("")
def list_exports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tasks = ExportService().list_tasks(db, current_user)
    return {"data": [serialize_export_task(task) for task in tasks]}


@router.get("/{export_id}")
def get_export(
    export_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    task = ExportService().get_task(db, export_id, current_user)
    return {"data": serialize_export_task(task)}


@router.get("/{export_id}/download")
def download_export(
    export_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ExportService()
    task = service.get_task(db, export_id, current_user)
    export_root = Path(request.app.state.settings.export_path)
    path = service.download_path(task, export_root)
    media_type = {
        "json": "application/json",
        "csv": "text/csv; charset=utf-8",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(task.format.value, "application/octet-stream")
    return FileResponse(path, media_type=media_type, filename=path.name)
