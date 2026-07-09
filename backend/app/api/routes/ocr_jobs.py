from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.domain.file.models import DocumentStatus
from app.domain.ocr.models import OcrJob, OcrJobStatus
from app.domain.user.models import User, UserRole
from app.workers.tasks import process_ocr_job_task


router = APIRouter(prefix="/api/v1/ocr-jobs", tags=["ocr-jobs"])


@router.get("/{job_id}")
def get_ocr_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    job = _get_job(db, job_id, current_user)
    return {"data": serialize_ocr_job_detail(job)}


@router.post("/{job_id}/retry")
def retry_ocr_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    job = _get_job(db, job_id, current_user)
    if job.status == OcrJobStatus.completed:
        return {"data": serialize_ocr_job_detail(job)}

    job.status = OcrJobStatus.queued
    job.attempt_count = 0
    job.error_code = None
    job.error_message = None
    job.provider_error_code = None
    job.next_retry_at = None
    job.finished_at = None
    job.document.status = DocumentStatus.ocr_queued
    db.commit()
    db.refresh(job)
    process_ocr_job_task.delay(str(job.id))
    return {"data": serialize_ocr_job_detail(job)}


@router.post("/{job_id}/cancel")
def cancel_ocr_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    job = _get_job(db, job_id, current_user)
    if job.status not in {OcrJobStatus.completed, OcrJobStatus.failed_final, OcrJobStatus.canceled}:
        job.status = OcrJobStatus.canceled
        job.document.status = DocumentStatus.ocr_failed
        db.commit()
        db.refresh(job)
    return {"data": serialize_ocr_job_detail(job)}


def _get_job(db: Session, job_id: UUID, current_user: User) -> OcrJob:
    job = db.get(
        OcrJob,
        job_id,
        options=[selectinload(OcrJob.document), selectinload(OcrJob.invoice)],
    )
    if job is None:
        raise AppError("OCR_JOB_NOT_FOUND", "OCR job was not found", status_code=404)
    if current_user.role in {UserRole.finance, UserRole.admin}:
        return job
    if str(job.document.uploaded_by) != str(current_user.id):
        raise AppError("AUTH_FORBIDDEN", "You do not have permission to access this OCR job", status_code=403)
    return job


def serialize_ocr_job_detail(job: OcrJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "document_id": str(job.document_id),
        "invoice_id": str(job.invoice_id) if job.invoice_id else None,
        "provider": job.provider,
        "action": job.action,
        "status": job.status.value,
        "attempt_count": job.attempt_count,
        "request_id": job.request_id,
        "error_code": job.error_code,
        "provider_error_code": job.provider_error_code,
        "error_message": job.error_message,
        "retryable": job.status in {OcrJobStatus.failed_final, OcrJobStatus.retry_scheduled},
        "next_retry_at": job.next_retry_at.isoformat() if job.next_retry_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }
