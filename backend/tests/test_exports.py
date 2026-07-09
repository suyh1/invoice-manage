import csv
import io
import json
import zipfile
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, import_all_models
from app.db.session import get_db
from app.domain.export.models import ExportFormat, ExportStatus, ExportTask
from app.domain.export.service import run_export_task
from app.domain.file.models import DocumentStatus, InvoiceDocument
from app.domain.invoice.models import Invoice, InvoiceItem, InvoiceStatus
from app.domain.ocr.models import OcrJob, OcrJobStatus, OcrProviderConfig, QuotaSource
from app.domain.user.models import AuditLog, UserRole
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
    session_local = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return session_local()


def make_client(session: Session, export_path) -> TestClient:
    app = create_app()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    app.state.settings.export_path = export_path
    return TestClient(app)


def seed_invoice(session: Session, *, user, status: InvoiceStatus = InvoiceStatus.confirmed) -> Invoice:
    provider = OcrProviderConfig(
        provider="tencent",
        display_name="Tencent OCR",
        enabled=True,
        is_default=False,
        quota_source=QuotaSource.manual,
    )
    document = InvoiceDocument(
        uploaded_by=user.id,
        original_filename="invoice.png",
        content_type="image/png",
        file_ext="png",
        file_size=100,
        base64_size=136,
        sha256="a" * 64,
        storage_key="2026/07/invoice.png",
        page_count=1,
        image_width=120,
        image_height=80,
        status=DocumentStatus.ocr_done,
    )
    job = OcrJob(
        document=document,
        provider_config=provider,
        provider="tencent",
        endpoint="ocr.tencentcloudapi.com",
        action="VatInvoiceOCR",
        version="2018-11-19",
        region="ap-guangzhou",
        status=OcrJobStatus.completed,
        attempt_count=1,
        idempotency_key="export-job",
        request_id="req-export-001",
        raw_request_meta={"duration_ms": 321},
    )
    invoice = Invoice(
        document=document,
        latest_ocr_job=job,
        invoice_type="增值税电子普通发票",
        invoice_code="144032216011",
        invoice_number="12876543",
        invoice_date=date(2026, 7, 9),
        seller_name="上海云栖酒店",
        buyer_name="星河科技有限公司",
        amount_without_tax=Decimal("688.00"),
        tax_amount=Decimal("41.28"),
        amount_with_tax=Decimal("729.28"),
        currency="CNY",
        expense_scene="travel",
        status=status,
    )
    invoice.items.append(InvoiceItem(name="住宿服务", amount=Decimal("688.00"), tax_rate=Decimal("0.0600")))
    session.add(invoice)
    session.commit()
    return invoice


def test_create_list_detail_and_download_json_export(tmp_path) -> None:
    with make_session() as session:
        user = create_user(session, email="user@example.com", password="password", display_name="User", role=UserRole.user)
        seed_invoice(session, user=user)
        client = make_client(session, tmp_path)
        client.cookies.set("session", create_session_token(user.id))

        create_response = client.post(
            "/api/v1/exports",
            json={
                "format": "json",
                "scope": "filtered_invoices",
                "filters": {"status": ["confirmed"]},
                "include_items": True,
                "include_ocr_meta": True,
            },
        )

        assert create_response.status_code == 200
        export_id = create_response.json()["data"]["id"]
        task = session.get(ExportTask, UUID(export_id))
        assert task.status == ExportStatus.queued
        assert task.created_by == user.id
        audit = session.scalar(select(AuditLog).where(AuditLog.action == "export.create"))
        assert audit is not None
        assert audit.actor_id == user.id
        assert audit.resource_type == "export_task"
        assert audit.resource_id == task.id
        assert audit.audit_metadata["format"] == "json"

        run_export_task(task.id, db=session, export_root=tmp_path)
        list_response = client.get("/api/v1/exports")
        detail_response = client.get(f"/api/v1/exports/{export_id}")
        download_response = client.get(f"/api/v1/exports/{export_id}/download")

        assert list_response.status_code == 200
        assert list_response.json()["data"][0]["id"] == export_id
        assert detail_response.status_code == 200
        assert detail_response.json()["data"]["status"] == "completed"
        assert download_response.status_code == 200
        payload = download_response.json()
        assert payload["export_metadata"]["format"] == "json"
        assert payload["invoices"][0]["invoice_number"] == "12876543"
        assert payload["items"][0]["name"] == "住宿服务"
        assert payload["ocr_jobs"][0]["request_id"] == "req-export-001"


def test_run_export_task_writes_csv_and_xlsx_files(tmp_path) -> None:
    with make_session() as session:
        finance = create_user(
            session, email="finance@example.com", password="password", display_name="Finance", role=UserRole.finance
        )
        seed_invoice(session, user=finance)
        csv_task = ExportTask(
            format=ExportFormat.csv,
            filters={"status": ["confirmed"], "include_items": False, "include_ocr_meta": False},
            status=ExportStatus.queued,
            created_by=finance.id,
        )
        xlsx_task = ExportTask(
            format=ExportFormat.xlsx,
            filters={"status": ["confirmed"], "include_items": True, "include_ocr_meta": True},
            status=ExportStatus.queued,
            created_by=finance.id,
        )
        session.add_all([csv_task, xlsx_task])
        session.commit()

        run_export_task(csv_task.id, db=session, export_root=tmp_path)
        run_export_task(xlsx_task.id, db=session, export_root=tmp_path)

        csv_content = (tmp_path / session.get(ExportTask, csv_task.id).storage_key).read_text()
        rows = list(csv.DictReader(io.StringIO(csv_content)))
        assert rows[0]["invoice_number"] == "12876543"
        assert rows[0]["amount_with_tax"] == "729.28"

        xlsx_path = tmp_path / session.get(ExportTask, xlsx_task.id).storage_key
        with zipfile.ZipFile(xlsx_path) as archive:
            workbook = archive.read("xl/workbook.xml").decode("utf-8")
            assert "Invoices" in workbook
            assert "Items" in workbook
            assert "OCR Jobs" in workbook
            assert "Export Metadata" in workbook


def test_export_download_requires_owner_or_finance_and_not_expired(tmp_path) -> None:
    with make_session() as session:
        owner = create_user(session, email="owner@example.com", password="password", display_name="Owner", role=UserRole.user)
        other = create_user(session, email="other@example.com", password="password", display_name="Other", role=UserRole.user)
        finance = create_user(
            session, email="finance@example.com", password="password", display_name="Finance", role=UserRole.finance
        )
        task = ExportTask(
            format=ExportFormat.json,
            status=ExportStatus.completed,
            storage_key="exports/expired.json",
            created_by=owner.id,
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        (tmp_path / "exports").mkdir()
        (tmp_path / "exports" / "expired.json").write_text(json.dumps({"expired": True}))
        session.add(task)
        session.commit()
        client = make_client(session, tmp_path)

        client.cookies.set("session", create_session_token(other.id))
        forbidden = client.get(f"/api/v1/exports/{task.id}/download")
        assert forbidden.status_code == 403

        client.cookies.set("session", create_session_token(finance.id))
        expired = client.get(f"/api/v1/exports/{task.id}/download")
        assert expired.status_code == 410
        assert expired.json()["error"]["code"] == "EXPORT_EXPIRED"
