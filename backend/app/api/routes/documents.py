from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.domain.file.models import DocumentStatus, InvoiceDocument
from app.domain.file.storage import LocalFileStorage
from app.domain.file.validators import ValidatedUpload, validate_upload
from app.domain.ocr.models import OcrJob, OcrJobStatus, OcrProviderConfig
from app.domain.user.models import User


router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    scene: str | None = Form(default=None),
    auto_ocr: bool = Form(default=True),
    idempotency_key: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, Any]]:
    del scene

    content = await file.read()
    validated = validate_upload(file.filename or "upload.bin", file.content_type, content)
    storage = LocalFileStorage(get_settings().storage_path)
    storage_key = storage.save(validated)

    document = InvoiceDocument(
        uploaded_by=current_user.id,
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
        status=DocumentStatus.uploaded,
    )
    db.add(document)

    ocr_job: OcrJob | None = None
    provider = find_default_ocr_provider(db) if auto_ocr else None
    if provider is not None:
        document.status = DocumentStatus.ocr_queued
        ocr_job = build_ocr_job(document, provider, validated, idempotency_key=idempotency_key)
        db.add(ocr_job)

    db.commit()
    db.refresh(document)

    return {
        "data": {
            "document_id": str(document.id),
            "ocr_job_id": str(ocr_job.id) if ocr_job is not None else None,
            "status": document.status.value,
            "sha256": document.sha256,
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
        },
    )
