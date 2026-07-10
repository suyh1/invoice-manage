from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, import_all_models
from app.db.session import get_db
from app.domain.file.models import DocumentStatus, InvoiceDocument
from app.domain.invoice.models import Invoice, InvoiceStatus
from app.domain.ocr.models import OcrJob, OcrJobStatus, OcrProviderConfig, QuotaSource
from app.domain.project.service import ProjectService
from app.domain.user.models import AuditLog, User, UserRole
from app.domain.user.service import create_session_token, create_user
from app.main import create_app


def make_session() -> Session:
    import_all_models()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()


def make_client(session: Session, user: User) -> TestClient:
    app = create_app()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    client.cookies.set("session", create_session_token(user.id, user.session_version))
    return client


def seed_review_data(session: Session, owner: User) -> tuple[Invoice, Invoice, InvoiceDocument]:
    project = ProjectService().ensure_uncategorized(session)
    provider = OcrProviderConfig(
        provider="mock",
        display_name="Mock OCR",
        enabled=True,
        is_default=False,
        quota_source=QuotaSource.manual,
    )
    needs_document = make_document(owner, project, "needs.png", DocumentStatus.ocr_done)
    duplicate_document = make_document(owner, project, "duplicate.png", DocumentStatus.ocr_done)
    failed_document = make_document(owner, project, "failed.png", DocumentStatus.ocr_failed)
    needs = Invoice(
        document=needs_document,
        invoice_number="1001",
        amount_with_tax=Decimal("100.00"),
        status=InvoiceStatus.needs_review,
    )
    duplicate = Invoice(
        document=duplicate_document,
        invoice_number="1002",
        amount_with_tax=Decimal("200.00"),
        status=InvoiceStatus.duplicate_suspected,
        is_duplicate_suspected=True,
    )
    failed_job = OcrJob(
        document=failed_document,
        provider_config=provider,
        provider="mock",
        endpoint="mock",
        action="VatInvoiceOCR",
        version="2018-11-19",
        status=OcrJobStatus.failed_final,
        attempt_count=3,
        idempotency_key=f"failed-job-{owner.id}",
        error_code="OCR_PROVIDER_TIMEOUT",
        provider_error_code="InternalError.Timeout",
        error_message="timeout",
        finished_at=datetime.now(UTC),
    )
    session.add_all([provider, needs, duplicate, failed_document, failed_job])
    session.commit()
    return needs, duplicate, failed_document


def make_document(owner: User, project, filename: str, status: DocumentStatus) -> InvoiceDocument:
    return InvoiceDocument(
        project=project,
        uploaded_by=owner.id,
        original_filename=filename,
        content_type="image/png",
        file_ext="png",
        file_size=100,
        base64_size=136,
        sha256=(filename.replace(".", "") + "0" * 64)[:64],
        storage_key=f"2026/07/{filename}",
        page_count=1,
        image_width=120,
        image_height=80,
        status=status,
    )


def test_review_summary_and_queues_include_failed_documents() -> None:
    with make_session() as session:
        owner = create_user(session, email="owner@example.com", password="password", display_name="Owner", role=UserRole.user)
        needs, duplicate, failed_document = seed_review_data(session, owner)
        client = make_client(session, owner)

        summary = client.get("/api/v1/review/summary")
        needs_queue = client.get("/api/v1/review/items?queue=needs_review")
        duplicate_queue = client.get("/api/v1/review/items?queue=duplicates")
        failed_queue = client.get("/api/v1/review/items?queue=failed")

        assert summary.status_code == 200
        assert summary.json()["data"] == {"needs_review": 1, "duplicates": 1, "failed": 1}
        assert needs_queue.json()["data"]["items"][0]["invoice_id"] == str(needs.id)
        assert duplicate_queue.json()["data"]["items"][0]["invoice_id"] == str(duplicate.id)
        failed_item = failed_queue.json()["data"]["items"][0]
        assert failed_item["kind"] == "document"
        assert failed_item["document_id"] == str(failed_document.id)
        assert failed_item["ocr"]["status"] == "failed_final"
        assert failed_item["ocr"]["provider_error_code"] == "InternalError.Timeout"


def test_review_queue_is_owner_scoped_for_normal_users_and_global_for_finance() -> None:
    with make_session() as session:
        owner = create_user(session, email="owner@example.com", password="password", display_name="Owner", role=UserRole.user)
        other = create_user(session, email="other@example.com", password="password", display_name="Other", role=UserRole.user)
        finance = create_user(session, email="finance@example.com", password="password", display_name="Finance", role=UserRole.finance)
        seed_review_data(session, owner)
        seed_review_data(session, other)

        owner_summary = make_client(session, owner).get("/api/v1/review/summary")
        finance_summary = make_client(session, finance).get("/api/v1/review/summary")

        assert owner_summary.json()["data"] == {"needs_review": 1, "duplicates": 1, "failed": 1}
        assert finance_summary.json()["data"] == {"needs_review": 2, "duplicates": 2, "failed": 2}


def test_bulk_confirm_confirms_clean_review_invoices_and_rejects_duplicates() -> None:
    with make_session() as session:
        owner = create_user(session, email="owner@example.com", password="password", display_name="Owner", role=UserRole.user)
        needs, duplicate, _ = seed_review_data(session, owner)
        client = make_client(session, owner)

        rejected = client.post(
            "/api/v1/invoices/bulk-confirm",
            json={"invoice_ids": [str(needs.id), str(duplicate.id)]},
        )

        assert rejected.status_code == 409
        assert rejected.json()["error"]["code"] == "REVIEW_BULK_CONFIRM_BLOCKED"
        session.refresh(needs)
        assert needs.status == InvoiceStatus.needs_review

        confirmed = client.post(
            "/api/v1/invoices/bulk-confirm",
            json={"invoice_ids": [str(needs.id)]},
        )

        assert confirmed.status_code == 200
        assert confirmed.json()["data"]["confirmed_ids"] == [str(needs.id)]
        session.refresh(needs)
        assert needs.status == InvoiceStatus.confirmed
        audits = session.query(AuditLog).filter(AuditLog.action.in_(["invoice.confirm", "invoice.bulk_confirm"])).all()
        assert {audit.action for audit in audits} == {"invoice.confirm", "invoice.bulk_confirm"}
