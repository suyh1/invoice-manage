from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import AppError
from app.db.base import Base, import_all_models
from app.domain.file.models import DocumentStatus, InvoiceDocument
from app.domain.invoice.models import Invoice, InvoiceItem, InvoiceStatus
from app.domain.ocr.client import OcrRecognitionResult
from app.domain.ocr.models import OcrJob, OcrJobStatus, OcrProviderUsageDaily
from app.domain.ocr.provider_config import OcrProviderConfigService
from app.domain.project.service import ProjectService
from app.domain.user.models import AuditLog, UserRole
from app.domain.user.service import create_user
from app.workers.tasks import process_ocr_job


class AllowingLimiter:
    def acquire(self, provider: str, region: str | None, action: str, qps_limit: int):
        return SimpleNamespace(allowed=True, retry_after_seconds=0.0)


class FakeRegistry:
    def __init__(self, client) -> None:
        self.client = client

    def get_client(self, provider_name: str):
        return self.client


def make_session() -> Session:
    import_all_models()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return session_local()


def seed_ocr_job(session: Session, storage_root: Path, *, attempt_count: int = 0) -> OcrJob:
    actor = create_user(
        session,
        email="admin@example.com",
        password="password",
        display_name="Admin",
        role=UserRole.admin,
    )
    provider = OcrProviderConfigService().create_config(
        session,
        {
            "provider": "tencent",
            "display_name": "Tencent OCR",
            "enabled": True,
            "is_default": True,
            "credential": {"secret_id": "AKID", "secret_key": "SECRET"},
            "quota": {"source": "estimated", "free_quota_total": 100, "free_quota_used": 5},
        },
        actor=actor,
    )
    storage_key = "2026/07/invoice.png"
    (storage_root / "2026" / "07").mkdir(parents=True)
    (storage_root / storage_key).write_bytes(b"invoice-image-bytes")
    document = InvoiceDocument(
        project=ProjectService().ensure_uncategorized(session),
        uploaded_by=actor.id,
        original_filename="invoice.png",
        content_type="image/png",
        file_ext="png",
        file_size=19,
        base64_size=28,
        sha256="a" * 64,
        storage_key=storage_key,
        page_count=1,
        image_width=120,
        image_height=80,
        status=DocumentStatus.ocr_queued,
    )
    job = OcrJob(
        document=document,
        provider_config=provider,
        provider=provider.provider,
        endpoint=provider.endpoint,
        action=provider.action,
        version=provider.api_version,
        region=provider.region,
        status=OcrJobStatus.queued,
        attempt_count=attempt_count,
        idempotency_key=f"job-{attempt_count}",
        raw_request_meta={"sha256": document.sha256, "file_ext": document.file_ext, "pdf_page_number": None},
    )
    session.add_all([document, job])
    session.commit()
    return job


def test_process_ocr_job_completes_and_normalizes_invoice(tmp_path) -> None:
    with make_session() as session:
        job = seed_ocr_job(session, tmp_path)
        payload = {
            "VatInvoiceInfos": [
                {"Name": "发票号码", "Value": "12876543"},
                {"Name": "开票日期", "Value": "2026-07-09"},
                {"Name": "销售方名称", "Value": "上海云栖酒店"},
            ],
            "Items": [{"Name": "住宿服务", "Amount": "688.00", "TaxRate": "6%"}],
            "RequestId": "req-success-001",
        }

        class SuccessfulClient:
            def recognize_file(self, provider_config, credential, upload):
                assert credential == {"secret_id": "AKID", "secret_key": "SECRET"}
                assert upload.content == b"invoice-image-bytes"
                return OcrRecognitionResult(raw_response=payload, request_id="req-success-001")

        processed = process_ocr_job(
            job.id,
            db=session,
            storage_root=tmp_path,
            registry=FakeRegistry(SuccessfulClient()),
            rate_limiter=AllowingLimiter(),
            now=datetime(2026, 7, 9, 12, 0, tzinfo=UTC),
        )

        assert processed.status == OcrJobStatus.completed
        assert processed.request_id == "req-success-001"
        assert processed.attempt_count == 1
        assert processed.raw_response == payload
        assert processed.raw_request_meta["duration_ms"] >= 0
        assert processed.document.status == DocumentStatus.ocr_done

        invoice = session.scalar(select(Invoice))
        assert invoice is not None
        assert invoice.status == InvoiceStatus.needs_review
        assert invoice.invoice_number == "12876543"
        assert invoice.seller_name == "上海云栖酒店"
        assert invoice.raw_ocr_payload == payload
        assert invoice.normalized_payload["invoice_fields"]["invoice_date"] == "2026-07-09"
        item = session.scalar(select(InvoiceItem))
        assert item.amount == Decimal("688.00")
        assert item.tax_rate == Decimal("0.0600")

        usage = session.scalar(select(OcrProviderUsageDaily))
        assert usage.successful_calls == 1
        assert usage.estimated_billable_calls == 1
        audit = session.scalar(select(AuditLog).where(AuditLog.action == "ocr.completed"))
        assert audit is not None
        assert audit.actor_id == job.document.uploaded_by
        assert audit.resource_type == "ocr_job"
        assert audit.resource_id == job.id
        assert audit.audit_metadata["request_id"] == "req-success-001"


def test_process_ocr_job_schedules_retry_for_retryable_provider_error(tmp_path) -> None:
    with make_session() as session:
        job = seed_ocr_job(session, tmp_path)
        now = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)

        class FailingClient:
            def recognize_file(self, provider_config, credential, upload):
                raise AppError(
                    "OCR_PROVIDER_RATE_LIMITED",
                    "rate limited",
                    status_code=503,
                    retryable=True,
                    provider="tencent",
                    provider_code="RequestLimitExceeded",
                    provider_request_id="req-limited-001",
                )

        processed = process_ocr_job(
            job.id,
            db=session,
            storage_root=tmp_path,
            registry=FakeRegistry(FailingClient()),
            rate_limiter=AllowingLimiter(),
            now=now,
        )

        assert processed.status == OcrJobStatus.retry_scheduled
        assert processed.attempt_count == 1
        assert processed.next_retry_at == now + timedelta(seconds=10)
        assert processed.error_code == "OCR_PROVIDER_RATE_LIMITED"
        assert processed.provider_error_code == "RequestLimitExceeded"
        assert processed.request_id == "req-limited-001"
        assert processed.document.status == DocumentStatus.ocr_queued
        assert session.scalar(select(OcrProviderUsageDaily)).failed_calls == 1


def test_process_ocr_job_marks_final_failure_for_non_retryable_error(tmp_path) -> None:
    with make_session() as session:
        job = seed_ocr_job(session, tmp_path)

        class FailingClient:
            def recognize_file(self, provider_config, credential, upload):
                raise AppError(
                    "OCR_PROVIDER_AUTH_FAILED",
                    "bad credentials",
                    status_code=502,
                    retryable=False,
                    provider="tencent",
                    provider_code="AuthFailure.SecretIdNotFound",
                    provider_request_id="req-auth-001",
                )

        processed = process_ocr_job(
            job.id,
            db=session,
            storage_root=tmp_path,
            registry=FakeRegistry(FailingClient()),
            rate_limiter=AllowingLimiter(),
            now=datetime(2026, 7, 9, 12, 0, tzinfo=UTC),
        )

        assert processed.status == OcrJobStatus.failed_final
        assert processed.attempt_count == 1
        assert processed.next_retry_at is None
        assert processed.error_code == "OCR_PROVIDER_AUTH_FAILED"
        assert processed.document.status == DocumentStatus.ocr_failed


def test_process_ocr_job_marks_final_failure_when_retry_attempts_are_exhausted(tmp_path) -> None:
    with make_session() as session:
        job = seed_ocr_job(session, tmp_path, attempt_count=2)

        class FailingClient:
            def recognize_file(self, provider_config, credential, upload):
                raise AppError(
                    "OCR_PROVIDER_TIMEOUT",
                    "timeout",
                    status_code=503,
                    retryable=True,
                    provider="tencent",
                    provider_code="InternalError.Timeout",
                )

        processed = process_ocr_job(
            job.id,
            db=session,
            storage_root=tmp_path,
            registry=FakeRegistry(FailingClient()),
            rate_limiter=AllowingLimiter(),
            now=datetime(2026, 7, 9, 12, 0, tzinfo=UTC),
        )

        assert processed.status == OcrJobStatus.failed_final
        assert processed.attempt_count == 3
        assert processed.next_retry_at is None
        assert processed.error_code == "OCR_PROVIDER_TIMEOUT"
