from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.audit import record_audit_log
from app.core.config import OCR_RETRY_DEFAULTS, get_settings
from app.core.errors import AppError
from app.db.session import SessionLocal
from app.domain.file.models import DocumentStatus, InvoiceDocument
from app.domain.file.validators import ValidatedUpload
from app.domain.invoice.models import Invoice, InvoiceItem, InvoiceStatus
from app.domain.ocr.client import OcrRecognitionResult
from app.domain.ocr.mapper import TencentVatInvoiceMapper
from app.domain.ocr.models import OcrJob, OcrJobStatus, OcrProviderConfig
from app.domain.ocr.provider_config import OcrProviderConfigService
from app.domain.ocr.quota import record_provider_call, sync_quota_alerts
from app.domain.ocr.rate_limiter import RedisTokenBucketRateLimiter, effective_qps
from app.domain.ocr.registry import get_registry
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.run_export_task")
def run_export_task_task(task_id: str) -> str:
    from app.domain.export.service import run_export_task

    with SessionLocal() as session:
        task = run_export_task(task_id, db=session)
        return str(task.id)


@celery_app.task(name="app.workers.process_ocr_job", bind=True)
def process_ocr_job_task(self, job_id: str) -> str:
    job = process_ocr_job(job_id)
    if job.status == OcrJobStatus.retry_scheduled and job.next_retry_at is not None:
        countdown = max(int((job.next_retry_at - datetime.now(UTC)).total_seconds()), 1)
        raise self.retry(countdown=countdown)
    return str(job.id)


def process_ocr_job(
    job_id: UUID | str,
    *,
    db: Session | None = None,
    storage_root: Path | None = None,
    registry=None,
    rate_limiter=None,
    now: datetime | None = None,
) -> OcrJob:
    if db is None:
        with SessionLocal() as session:
            return process_ocr_job(
                job_id,
                db=session,
                storage_root=storage_root,
                registry=registry,
                rate_limiter=rate_limiter,
                now=now,
            )

    now = now or datetime.now(UTC)
    job = db.get(OcrJob, job_id)
    if job is None:
        raise AppError("OCR_JOB_NOT_FOUND", "OCR job was not found", status_code=404)
    if job.status in {OcrJobStatus.completed, OcrJobStatus.failed_final, OcrJobStatus.canceled}:
        return job

    provider_config = job.provider_config
    decision = _rate_limiter(rate_limiter).acquire(
        provider_config.provider,
        provider_config.region,
        provider_config.action,
        effective_qps(provider_config),
    )
    if not decision.allowed:
        job.status = OcrJobStatus.retry_scheduled
        job.next_retry_at = now + timedelta(seconds=decision.retry_after_seconds)
        job.error_code = "OCR_LOCAL_RATE_LIMITED"
        job.error_message = "OCR worker local rate limit was reached"
        job.document.status = DocumentStatus.ocr_queued
        db.commit()
        return job

    job.status = OcrJobStatus.running
    job.started_at = now
    job.attempt_count += 1
    job.document.status = DocumentStatus.ocr_running
    db.flush()

    start_time = time.perf_counter()
    try:
        result = _recognize(job, provider_config, storage_root=storage_root, registry=registry)
    except AppError as exc:
        _record_duration(job, start_time)
        record_provider_call(db, provider_config, success=False, usage_date=now.date())
        sync_quota_alerts(db, provider_config)
        _apply_provider_failure(job, exc, now=now)
        db.commit()
        return job
    except Exception as exc:
        _record_duration(job, start_time)
        app_error = AppError(
            "OCR_PROVIDER_UNKNOWN_ERROR",
            "OCR provider request failed unexpectedly",
            status_code=502,
            retryable=True,
        )
        record_provider_call(db, provider_config, success=False, usage_date=now.date())
        sync_quota_alerts(db, provider_config)
        _apply_provider_failure(job, app_error, now=now)
        db.commit()
        raise exc

    _record_duration(job, start_time)
    record_provider_call(db, provider_config, success=True, usage_date=now.date())
    sync_quota_alerts(db, provider_config)
    _apply_successful_result(db, job, result, now=now)
    db.commit()
    return job


def _recognize(
    job: OcrJob,
    provider_config: OcrProviderConfig,
    *,
    storage_root: Path | None,
    registry,
) -> OcrRecognitionResult:
    service = OcrProviderConfigService()
    credential = service.decrypt_credential(provider_config) or {}
    client = (registry or get_registry()).get_client(provider_config.provider)
    return client.recognize_file(provider_config, credential, _validated_upload_from_document(job.document, storage_root))


def _validated_upload_from_document(document: InvoiceDocument, storage_root: Path | None) -> ValidatedUpload:
    root = storage_root or get_settings().storage_path
    content = (root / document.storage_key).read_bytes()
    return ValidatedUpload(
        original_filename=document.original_filename,
        content_type=document.content_type,
        file_ext=document.file_ext,
        file_size=document.file_size,
        base64_size=document.base64_size,
        sha256=document.sha256,
        page_count=document.page_count or 1,
        image_width=document.image_width,
        image_height=document.image_height,
        content=content,
    )


def _apply_successful_result(db: Session, job: OcrJob, result: OcrRecognitionResult, *, now: datetime) -> None:
    job.status = OcrJobStatus.succeeded
    job.raw_response = result.raw_response
    job.request_id = result.request_id
    job.error_code = None
    job.provider_error_code = None
    job.error_message = None
    job.next_retry_at = None

    job.status = OcrJobStatus.normalizing
    mapped = TencentVatInvoiceMapper().map(result.raw_response)
    invoice = job.document.invoice or Invoice(document=job.document)
    if invoice.expense_scene is None:
        invoice.expense_scene = job.document.expense_scene
    for field, value in mapped.invoice_fields.items():
        setattr(invoice, field, value)
    invoice.latest_ocr_job = job
    invoice.raw_ocr_payload = mapped.raw_ocr_payload
    invoice.normalized_payload = mapped.normalized_payload
    invoice.extra_fields = mapped.extra_fields
    invoice.status = InvoiceStatus.needs_review
    invoice.items.clear()
    for mapped_item in mapped.items:
        item_payload = dict(mapped_item)
        raw_item_json = item_payload.pop("raw_item_json", None)
        invoice.items.append(InvoiceItem(**item_payload, raw_item_json=raw_item_json))
    db.add(invoice)

    job.invoice = invoice
    job.status = OcrJobStatus.completed
    job.finished_at = now
    job.document.status = DocumentStatus.ocr_done
    db.flush()
    record_audit_log(
        db,
        actor_id=job.document.uploaded_by,
        action="ocr.completed",
        resource_type="ocr_job",
        resource_id=job.id,
        metadata={
            "provider": job.provider,
            "request_id": job.request_id,
            "invoice_id": str(invoice.id),
            "duration_ms": (job.raw_request_meta or {}).get("duration_ms"),
        },
    )


def _apply_provider_failure(job: OcrJob, exc: AppError, *, now: datetime) -> None:
    job.error_code = exc.code
    job.provider_error_code = exc.provider_code
    job.request_id = exc.provider_request_id
    job.error_message = exc.message
    if exc.retryable and job.attempt_count < OCR_RETRY_DEFAULTS.max_attempts:
        job.status = OcrJobStatus.retry_scheduled
        job.next_retry_at = now + timedelta(seconds=_backoff_seconds(job.attempt_count))
        job.document.status = DocumentStatus.ocr_queued
        return

    job.status = OcrJobStatus.failed_final
    job.next_retry_at = None
    job.finished_at = now
    job.document.status = DocumentStatus.ocr_failed


def _backoff_seconds(attempt_count: int) -> int:
    index = max(attempt_count - 1, 0)
    return OCR_RETRY_DEFAULTS.backoff_seconds[min(index, len(OCR_RETRY_DEFAULTS.backoff_seconds) - 1)]


def _record_duration(job: OcrJob, start_time: float) -> None:
    meta: dict[str, Any] = dict(job.raw_request_meta or {})
    meta["duration_ms"] = int((time.perf_counter() - start_time) * 1000)
    job.raw_request_meta = meta


def _rate_limiter(rate_limiter):
    if rate_limiter is not None:
        return rate_limiter
    return RedisTokenBucketRateLimiter(make_redis_client())


def make_redis_client():
    import redis

    return redis.Redis.from_url(get_settings().redis_url)
