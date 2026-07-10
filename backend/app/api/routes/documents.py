from __future__ import annotations

import hashlib
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.audit import record_audit_log
from app.core.config import get_settings
from app.db.session import get_db
from app.domain.file.models import DocumentStatus, InvoiceDocument
from app.domain.file.storage import LocalFileStorage
from app.domain.file.validators import ValidatedUpload, validate_upload
from app.domain.ocr.models import OcrJob, OcrJobStatus, OcrProviderConfig
from app.domain.project.service import ProjectService
from app.domain.user.models import User
from app.workers.tasks import process_ocr_job_task


router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
logger = logging.getLogger(__name__)


@router.post("")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    scene: str | None = Form(default=None),
    project_id: UUID | None = Form(default=None),
    auto_ocr: bool = Form(default=True),
    idempotency_key: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, Any]]:
    content = await file.read()
    validated = validate_upload(file.filename or "upload.bin", file.content_type, content)
    project = ProjectService().get_assignable_project(db, project_id, current_user)
    storage = LocalFileStorage(get_settings().storage_path)
    storage_key = storage.save(validated)

    document = InvoiceDocument(
        uploaded_by=current_user.id,
        project=project,
        original_filename=validated.original_filename,
        content_type=validated.content_type or "application/octet-stream",
        file_ext=validated.file_ext,
        file_size=validated.file_size,
        base64_size=validated.base64_size,
        sha256=validated.sha256,
        storage_key=storage_key,
        page_count=validated.page_count,
        image_width=validated.image_width,
        image_height=validated.image_height,
        expense_scene=scene.strip() if scene and scene.strip() else None,
        status=DocumentStatus.uploaded,
    )
    db.add(document)

    ocr_job: OcrJob | None = None
    provider = find_default_ocr_provider(db) if auto_ocr else None
    if provider is not None:
        document.status = DocumentStatus.ocr_queued
        ocr_job = build_ocr_job(document, provider, validated, idempotency_key=idempotency_key)
        db.add(ocr_job)

    db.flush()
    record_audit_log(
        db,
        actor=current_user,
        action="document.upload",
        resource_type="invoice_document",
        resource_id=document.id,
        metadata={
            "original_filename": document.original_filename,
            "file_ext": document.file_ext,
            "file_size": document.file_size,
            "sha256": document.sha256,
            "auto_ocr": auto_ocr,
            "project_id": str(project.id),
            "scene": document.expense_scene,
            "ocr_job_id": str(ocr_job.id) if ocr_job else None,
        },
        request=request,
    )
    db.commit()
    db.refresh(document)
    if ocr_job is not None:
        try:
            process_ocr_job_task.delay(str(ocr_job.id))
        except Exception as exc:
            logger.warning("failed to enqueue OCR job %s: %s", ocr_job.id, exc.__class__.__name__)

    return {
        "data": {
            "document_id": str(document.id),
            "ocr_job_id": str(ocr_job.id) if ocr_job is not None else None,
            "status": document.status.value,
            "sha256": document.sha256,
            "project": {
                "id": str(project.id),
                "name": project.name,
            },
        }
    }


def find_default_ocr_provider(db: Session) -> OcrProviderConfig | None:
    return db.scalar(select(OcrProviderConfig).where(OcrProviderConfig.enabled.is_(True), OcrProviderConfig.is_default.is_(True)))


def build_ocr_job(
    document: InvoiceDocument,
    provider: OcrProviderConfig,
    validated_upload: ValidatedUpload,
    *,
    idempotency_key: str | None,
) -> OcrJob:
    pdf_page_number = 1 if validated_upload.file_ext == "pdf" else None
    source = idempotency_key or f"{provider.id}:{provider.action}:{pdf_page_number or 0}:{validated_upload.sha256}"
    return OcrJob(
        document=document,
        provider_config_id=provider.id,
        provider=provider.provider,
        endpoint=provider.endpoint,
        action=provider.action,
        version=provider.api_version,
        region=provider.region,
        status=OcrJobStatus.queued,
        idempotency_key=hashlib.sha256(source.encode("utf-8")).hexdigest(),
        raw_request_meta={
            "sha256": validated_upload.sha256,
            "content_type": validated_upload.content_type,
            "file_ext": validated_upload.file_ext,
            "pdf_page_number": pdf_page_number,
            "expense_scene": document.expense_scene,
        },
    )
