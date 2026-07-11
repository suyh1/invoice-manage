import csv
import io
import json
import zipfile
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, import_all_models
from app.db.session import get_db
from app.domain.export.models import ExportFormat, ExportStatus, ExportTask
from app.domain.export.service import run_export_task
from app.domain.file.models import DocumentKind, DocumentStatus, InvoiceDocument
from app.domain.invoice.models import Invoice, InvoiceItem, InvoiceStatus
from app.domain.ocr.models import OcrJob, OcrJobStatus, OcrProviderConfig, QuotaSource
from app.domain.project.models import Project
from app.domain.project.service import ProjectService
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


def seed_invoice(
    session: Session,
    *,
    user,
    status: InvoiceStatus = InvoiceStatus.confirmed,
    project: Project | None = None,
    invoice_number: str = "12876543",
) -> Invoice:
    project = project or ProjectService().ensure_uncategorized(session)
    provider = OcrProviderConfig(
        provider="tencent",
        display_name="Tencent OCR",
        enabled=True,
        is_default=False,
        quota_source=QuotaSource.manual,
    )
    document = InvoiceDocument(
        project=project,
        uploaded_by=user.id,
        original_filename=f"{invoice_number}.png",
        content_type="image/png",
        file_ext="png",
        file_size=100,
        base64_size=136,
        sha256=(invoice_number + "a" * 64)[:64],
        storage_key=f"2026/07/{invoice_number}.png",
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
        idempotency_key=f"export-job-{invoice_number}",
        request_id="req-export-001" if invoice_number == "12876543" else f"req-export-{invoice_number}",
        raw_request_meta={"duration_ms": 321},
    )
    invoice = Invoice(
        document=document,
        latest_ocr_job=job,
        invoice_type="增值税电子普通发票",
        invoice_code="144032216011",
        invoice_number=invoice_number,
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


def seed_project_file(
    session: Session,
    *,
    user,
    project: Project,
    filename: str,
    storage_key: str,
    content: bytes,
) -> InvoiceDocument:
    document = InvoiceDocument(
        project=project,
        uploaded_by=user.id,
        document_kind=DocumentKind.project_file,
        original_filename=filename,
        content_type="application/pdf",
        file_ext="pdf",
        file_size=len(content),
        base64_size=len(content),
        sha256=(storage_key.replace("/", "") + "b" * 64)[:64],
        storage_key=storage_key,
        status=DocumentStatus.uploaded,
    )
    session.add(document)
    session.commit()
    return document


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


def test_export_filters_by_project_and_uploader_and_includes_project_metadata(tmp_path) -> None:
    with make_session() as session:
        owner = create_user(session, email="owner@example.com", password="password", display_name="Owner", role=UserRole.user)
        other = create_user(session, email="other@example.com", password="password", display_name="Other", role=UserRole.user)
        finance = create_user(
            session, email="finance@example.com", password="password", display_name="Finance", role=UserRole.finance
        )
        project_service = ProjectService()
        shared = project_service.create_project(session, finance, {"name": "共享差旅", "visibility": "shared"})
        other_private = project_service.create_project(session, other, {"name": "他人私有", "visibility": "private"})
        seed_invoice(session, user=owner, project=shared, invoice_number="10000001")
        seed_invoice(session, user=other, project=other_private, invoice_number="10000002")
        task = ExportTask(
            format=ExportFormat.json,
            filters={
                "project_id": str(shared.id),
                "uploaded_by": str(owner.id),
                "include_items": True,
                "include_ocr_meta": True,
            },
            status=ExportStatus.queued,
            created_by=finance.id,
        )
        session.add(task)
        session.commit()

        run_export_task(task.id, db=session, export_root=tmp_path)
        payload = json.loads((tmp_path / task.storage_key).read_text())
        serialized = make_client(session, tmp_path)
        serialized.cookies.set("session", create_session_token(finance.id))
        task_response = serialized.get(f"/api/v1/exports/{task.id}")

        assert payload["export_metadata"]["invoice_count"] == 1
        assert payload["invoices"][0]["invoice_number"] == "10000001"
        assert payload["invoices"][0]["project_id"] == str(shared.id)
        assert payload["invoices"][0]["project_name"] == "共享差旅"
        assert task_response.json()["data"]["created_by_user"] == {
            "id": str(finance.id),
            "display_name": "Finance",
            "email": "finance@example.com",
        }


def test_export_failure_persists_safe_error_message(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    with make_session() as session:
        user = create_user(session, email="user@example.com", password="password", display_name="User", role=UserRole.user)
        task = ExportTask(
            format=ExportFormat.json,
            filters={},
            status=ExportStatus.queued,
            created_by=user.id,
        )
        session.add(task)
        session.commit()

        def fail_render(*args, **kwargs):
            raise RuntimeError("failed while writing /data/exports/private.json")

        monkeypatch.setattr("app.domain.export.service.render_export", fail_render)

        with pytest.raises(RuntimeError):
            run_export_task(task.id, db=session, export_root=tmp_path)

        session.refresh(task)
        assert task.status == ExportStatus.failed
        assert task.error_message == "Export task failed (RuntimeError)"
        assert "/data/" not in task.error_message


def test_zip_export_requires_project_id(tmp_path) -> None:
    with make_session() as session:
        user = create_user(session, email="zip@example.com", password="password", display_name="Zip User", role=UserRole.user)
        client = make_client(session, tmp_path)
        client.cookies.set("session", create_session_token(user.id))

        response = client.post(
            "/api/v1/exports",
            json={"format": "zip", "scope": "project_files", "filters": {}},
        )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "EXPORT_PROJECT_REQUIRED"


def test_zip_export_packages_visible_project_documents_with_manifest_and_duplicate_names(tmp_path) -> None:
    with make_session() as session:
        owner = create_user(session, email="zip-owner@example.com", password="password", display_name="Zip Owner", role=UserRole.user)
        other = create_user(session, email="zip-other@example.com", password="password", display_name="Zip Other", role=UserRole.user)
        finance = create_user(session, email="zip-finance@example.com", password="password", display_name="Zip Finance", role=UserRole.finance)
        project = ProjectService().create_project(session, finance, {"name": "车辆资料", "visibility": "shared"})
        invoice = seed_invoice(session, user=owner, project=project, invoice_number="90000001")
        invoice.document.original_filename = "出租车票.pdf"
        invoice.document.content_type = "application/pdf"
        invoice.document.file_ext = "pdf"
        invoice.document.storage_key = "invoice/taxi.pdf"
        first = seed_project_file(
            session,
            user=owner,
            project=project,
            filename="行程单.pdf",
            storage_key="files/trip-1.pdf",
            content=b"trip-one",
        )
        second = seed_project_file(
            session,
            user=owner,
            project=project,
            filename="行程单.pdf",
            storage_key="files/trip-2.pdf",
            content=b"trip-two",
        )
        seed_project_file(
            session,
            user=other,
            project=project,
            filename="他人的资料.pdf",
            storage_key="files/other.pdf",
            content=b"other",
        )
        session.commit()
        upload_root = tmp_path / "uploads"
        for storage_key, content in {
            invoice.document.storage_key: b"invoice-original",
            first.storage_key: b"trip-one",
            second.storage_key: b"trip-two",
            "files/other.pdf": b"other",
        }.items():
            path = upload_root / storage_key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        task = ExportTask(
            format=ExportFormat.zip,
            filters={"scope": "project_files", "project_id": str(project.id)},
            status=ExportStatus.queued,
            created_by=owner.id,
        )
        session.add(task)
        session.commit()

        run_export_task(task.id, db=session, export_root=tmp_path / "exports", storage_root=upload_root)

        with zipfile.ZipFile(tmp_path / "exports" / task.storage_key) as archive:
            names = archive.namelist()
            assert "发票原件/出租车票.pdf" in names
            assert "项目文件/行程单.pdf" in names
            assert "项目文件/行程单 (2).pdf" in names
            assert all("他人的资料.pdf" not in name for name in names)
            manifest = json.loads(archive.read("manifest.json"))
        assert manifest["project"] == {"id": str(project.id), "name": "车辆资料"}
        assert manifest["file_count"] == 3
        assert {entry["document_kind"] for entry in manifest["files"]} == {"invoice", "project_file"}
        assert all(entry["archive_path"] in names for entry in manifest["files"])
        assert all("sha256" in entry and "uploaded_by" in entry for entry in manifest["files"])


def test_zip_export_fails_when_a_source_file_is_missing(tmp_path) -> None:
    with make_session() as session:
        owner = create_user(session, email="missing@example.com", password="password", display_name="Missing", role=UserRole.user)
        project = ProjectService().ensure_uncategorized(session)
        seed_project_file(
            session,
            user=owner,
            project=project,
            filename="缺失文件.pdf",
            storage_key="missing/file.pdf",
            content=b"missing",
        )
        task = ExportTask(
            format=ExportFormat.zip,
            filters={"scope": "project_files", "project_id": str(project.id)},
            status=ExportStatus.queued,
            created_by=owner.id,
        )
        session.add(task)
        session.commit()

        with pytest.raises(FileNotFoundError):
            run_export_task(
                task.id,
                db=session,
                export_root=tmp_path / "exports",
                storage_root=tmp_path / "uploads",
            )

        session.refresh(task)
        assert task.status == ExportStatus.failed
        assert task.error_message == "Export task failed (FileNotFoundError)"
