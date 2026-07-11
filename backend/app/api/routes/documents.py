from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_user
from app.core.audit import record_audit_log
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.domain.file.models import DocumentKind, DocumentStatus, InvoiceDocument
from app.domain.file.storage import LocalFileStorage
from app.domain.file.validators import ValidatedUpload, validate_project_file_upload, validate_upload
from app.domain.ocr.models import OcrJob, OcrJobStatus, OcrProviderConfig
from app.domain.project.service import ProjectService
from app.domain.user.models import User, UserRole
from app.workers.tasks import process_ocr_job_task


router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
logger = logging.getLogger(__name__)


@router.get("")
def list_documents(
    document_kind: DocumentKind = DocumentKind.project_file,
    project_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, list[dict[str, Any]]]:
    if document_kind != DocumentKind.project_file:
        raise AppError("PROJECT_FILE_REQUIRED", "Only project files can be listed here", status_code=409)
    statement = (
        select(InvoiceDocument)
        .options(selectinload(InvoiceDocument.project), selectinload(InvoiceDocument.uploaded_by_user))
        .where(
            InvoiceDocument.document_kind == DocumentKind.project_file,
            InvoiceDocument.status != DocumentStatus.deleted,
        )
        .order_by(InvoiceDocument.created_at.desc(), InvoiceDocument.id.desc())
    )
    if project_id is not None:
        statement = statement.where(InvoiceDocument.project_id == project_id)
    if current_user.role not in {UserRole.finance, UserRole.admin}:
        statement = statement.where(InvoiceDocument.uploaded_by == current_user.id)
    return {"data": [_serialize_project_file(document) for document in db.scalars(statement)]}


@router.get("/{document_id}/preview", response_class=FileResponse)
def preview_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    return _document_file_response(db, document_id, current_user, disposition="inline")


@router.get("/{document_id}/download", response_class=FileResponse)
def download_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    return _document_file_response(db, document_id, current_user, disposition="attachment")


@router.delete("/{document_id}")
def delete_project_file(
    document_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, bool]]:
    document = _get_document(db, document_id)
    if document.document_kind != DocumentKind.project_file:
        raise AppError("PROJECT_FILE_REQUIRED", "Only project files can be deleted here", status_code=409)
    _assert_document_access(document, current_user)
    document.status = DocumentStatus.deleted
    document.deleted_at = datetime.now(UTC)
    record_audit_log(
        db,
        actor=current_user,
        action="document.delete",
        resource_type="project_file",
        resource_id=document.id,
        metadata={"original_filename": document.original_filename, "project_id": str(document.project_id)},
        request=request,
    )
    db.commit()
    return {"data": {"ok": True}}


@router.post("")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    scene: str | None = Form(default=None),
    project_id: UUID | None = Form(default=None),
    document_kind: DocumentKind = Form(default=DocumentKind.invoice),
    auto_ocr: bool = Form(default=True),
    idempotency_key: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, Any]]:
    content = await file.read()
    if document_kind == DocumentKind.project_file and project_id is None:
        raise AppError(
            "PROJECT_FILE_PROJECT_REQUIRED",
            "Project files must be assigned to a project",
            status_code=400,
        )
    validated = (
        validate_project_file_upload(file.filename or "upload.bin", file.content_type, content)
        if document_kind == DocumentKind.project_file
        else validate_upload(file.filename or "upload.bin", file.content_type, content)
    )
    project = ProjectService().get_assignable_project(db, project_id, current_user)
    storage = LocalFileStorage(get_settings().storage_path)
    storage_key = storage.save(validated)

    document = InvoiceDocument(
        uploaded_by=current_user.id,
        project=project,
        document_kind=document_kind,
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
        expense_scene=(scene.strip() if scene and scene.strip() else None) if document_kind == DocumentKind.invoice else None,
        status=DocumentStatus.uploaded,
    )
    db.add(document)

    ocr_job: OcrJob | None = None
    if auto_ocr and document_kind == DocumentKind.invoice:
        document.status = DocumentStatus.ocr_queued
        ocr_job = build_ocr_job(document, validated, idempotency_key=idempotency_key)
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
            "document_kind": document.document_kind.value,
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
            "document_kind": document.document_kind.value,
            "sha256": document.sha256,
            "project": {
                "id": str(project.id),
                "name": project.name,
            },
        }
    }


def find_default_ocr_provider(db: Session) -> OcrProviderConfig | None:
    return db.scalar(select(OcrProviderConfig).where(OcrProviderConfig.enabled.is_(True), OcrProviderConfig.is_default.is_(True)))


def _document_file_response(
    db: Session,
    document_id: UUID,
    current_user: User,
    *,
    disposition: str,
) -> FileResponse:
    document = _get_document(db, document_id)
    _assert_document_access(document, current_user)

    try:
        path = LocalFileStorage(get_settings().storage_path).path_for(document.storage_key)
    except ValueError as exc:
        raise AppError("DOCUMENT_STORAGE_INVALID", "Document storage path is invalid", status_code=500) from exc
    if not path.is_file():
        raise AppError("DOCUMENT_FILE_MISSING", "Document file is missing from storage", status_code=404)
    return FileResponse(
        path,
        media_type=document.content_type,
        filename=document.original_filename,
        content_disposition_type=disposition,
    )


def _get_document(db: Session, document_id: UUID) -> InvoiceDocument:
    document = db.get(InvoiceDocument, document_id)
    if document is None or document.status == DocumentStatus.deleted:
        raise AppError("DOCUMENT_NOT_FOUND", "Document was not found", status_code=404)
    return document


def _assert_document_access(document: InvoiceDocument, current_user: User) -> None:
    if current_user.role in {UserRole.finance, UserRole.admin}:
        return
    if str(document.uploaded_by) == str(current_user.id):
        return
    raise AppError("AUTH_FORBIDDEN", "You do not have permission to access this document", status_code=403)


def _serialize_project_file(document: InvoiceDocument) -> dict[str, Any]:
    return {
        "id": str(document.id),
        "document_kind": document.document_kind.value,
        "original_filename": document.original_filename,
        "content_type": document.content_type,
        "file_ext": document.file_ext,
        "file_size": document.file_size,
        "sha256": document.sha256,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "project": {
            "id": str(document.project.id),
            "name": document.project.name,
        },
        "uploaded_by_user": {
            "id": str(document.uploaded_by_user.id),
            "display_name": document.uploaded_by_user.display_name,
            "email": document.uploaded_by_user.email,
        },
    }


def build_ocr_job(
    document: InvoiceDocument,
    validated_upload: ValidatedUpload,
    *,
    idempotency_key: str | None,
) -> OcrJob:
    pdf_page_number = 1 if validated_upload.file_ext == "pdf" else None
    source = idempotency_key or f"{pdf_page_number or 0}:{validated_upload.sha256}"
    return OcrJob(
        document=document,
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
