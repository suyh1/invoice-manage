from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, import_all_models
from app.db.session import get_db
from app.domain.export.models import ExportFormat, ExportStatus, ExportTask
from app.domain.file.models import DocumentStatus, InvoiceDocument
from app.domain.invoice.models import Invoice, InvoiceStatus
from app.domain.ocr.models import OcrJob, OcrJobStatus, OcrProviderConfig, QuotaSource
from app.domain.project.service import ProjectService
from app.domain.user.models import User, UserRole
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


def seed_dashboard_data(session: Session, owner: User) -> None:
    project = ProjectService().ensure_uncategorized(session)
    provider = OcrProviderConfig(
        provider="mock",
        display_name=f"Mock {owner.email}",
        enabled=True,
        is_default=False,
        quota_source=QuotaSource.manual,
    )
    review_document = make_document(owner, project, f"review-{owner.id}.png", DocumentStatus.ocr_done)
    confirmed_document = make_document(owner, project, f"confirmed-{owner.id}.png", DocumentStatus.ocr_done)
    failed_document = make_document(owner, project, f"failed-{owner.id}.png", DocumentStatus.ocr_failed)
    queued_document = make_document(owner, project, f"queued-{owner.id}.png", DocumentStatus.ocr_queued)
    review = Invoice(document=review_document, status=InvoiceStatus.needs_review, amount_with_tax=Decimal("10.00"))
    confirmed = Invoice(
        document=confirmed_document,
        status=InvoiceStatus.confirmed,
        amount_with_tax=Decimal("128.50"),
        confirmed_by=owner.id,
        confirmed_at=datetime.now(UTC) - timedelta(days=2),
    )
    failed_job = make_job(provider, failed_document, f"failed-{owner.id}", OcrJobStatus.failed_final)
    queued_job = make_job(provider, queued_document, f"queued-{owner.id}", OcrJobStatus.queued)
    export = ExportTask(
        format=ExportFormat.xlsx,
        status=ExportStatus.completed,
        created_by=owner.id,
        storage_key=f"exports/{owner.id}.xlsx",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    session.add_all([provider, review, confirmed, failed_document, queued_document, failed_job, queued_job, export])
    session.commit()


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


def make_job(provider, document, key: str, status: OcrJobStatus) -> OcrJob:
    return OcrJob(
        document=document,
        provider_config=provider,
        provider="mock",
        endpoint="mock",
        action="VatInvoiceOCR",
        version="2018-11-19",
        status=status,
        idempotency_key=key,
    )


def test_dashboard_summary_uses_real_role_scoped_data() -> None:
    with make_session() as session:
        owner = create_user(session, email="owner@example.com", password="password", display_name="Owner", role=UserRole.user)
        other = create_user(session, email="other@example.com", password="password", display_name="Other", role=UserRole.user)
        finance = create_user(session, email="finance@example.com", password="password", display_name="Finance", role=UserRole.finance)
        seed_dashboard_data(session, owner)
        seed_dashboard_data(session, other)

        owner_response = make_client(session, owner).get("/api/v1/dashboard/summary")
        finance_response = make_client(session, finance).get("/api/v1/dashboard/summary")

        assert owner_response.status_code == 200
        assert owner_response.json()["data"]["needs_review"] == 1
        assert owner_response.json()["data"]["ocr_failed"] == 1
        assert owner_response.json()["data"]["confirmed_amount_30d"] == "128.50"
        assert owner_response.json()["data"]["queued_ocr"] == 1
        assert len(owner_response.json()["data"]["recent_exports"]) == 1

        assert finance_response.status_code == 200
        assert finance_response.json()["data"]["needs_review"] == 2
        assert finance_response.json()["data"]["ocr_failed"] == 2
        assert finance_response.json()["data"]["confirmed_amount_30d"] == "257.00"
        assert finance_response.json()["data"]["queued_ocr"] == 2
        assert len(finance_response.json()["data"]["recent_exports"]) == 2
