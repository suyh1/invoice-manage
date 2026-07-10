import os
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.db.base import Base, import_all_models
from app.domain.export.models import ExportFormat, ExportStatus, ExportTask
from app.domain.file.models import DocumentStatus, InvoiceDocument
from app.domain.invoice.models import Invoice, InvoiceItem, InvoiceStatus
from app.domain.ocr.models import OcrJob, OcrJobStatus, OcrProviderConfig, QuotaSource
from app.domain.project.models import Project, ProjectStatus, ProjectVisibility
from app.domain.user.models import User, UserRole, UserStatus


EXPECTED_TABLES = {
    "audit_logs",
    "duplicate_checks",
    "export_tasks",
    "invoice_corrections",
    "invoice_documents",
    "invoice_items",
    "invoices",
    "ocr_jobs",
    "ocr_provider_configs",
    "ocr_provider_usage_daily",
    "ocr_quota_alerts",
    "projects",
    "system_state",
    "users",
}


def test_metadata_contains_design_tables() -> None:
    import_all_models()

    assert EXPECTED_TABLES.issubset(Base.metadata.tables.keys())


def test_core_indexes_and_unique_constraints_are_declared() -> None:
    import_all_models()

    provider_table = Base.metadata.tables["ocr_provider_configs"]
    usage_table = Base.metadata.tables["ocr_provider_usage_daily"]
    jobs_table = Base.metadata.tables["ocr_jobs"]
    documents_table = Base.metadata.tables["invoice_documents"]
    projects_table = Base.metadata.tables["projects"]

    assert {"provider_config_id", "usage_date", "action"} in [
        set(constraint.columns.keys()) for constraint in usage_table.constraints if constraint.name
    ]
    assert "ix_ocr_provider_configs_single_default" in {index.name for index in provider_table.indexes}
    assert "uq_ocr_jobs_idempotency_key" in {constraint.name for constraint in jobs_table.constraints}
    assert "ix_invoice_documents_sha256" in {index.name for index in documents_table.indexes}
    assert documents_table.c.project_id.nullable is False
    assert "ix_invoice_documents_project_id_created_at" in {index.name for index in documents_table.indexes}
    assert "system_key" in {constraint.name or "" for constraint in projects_table.constraints} or any(
        column.unique for column in projects_table.columns if column.name == "system_key"
    )


def test_models_create_and_persist_against_postgresql() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL model integration test")

    import_all_models()
    engine = create_engine(database_url)

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    assert EXPECTED_TABLES.issubset(set(inspector.get_table_names()))

    with Session(engine) as session:
        user = User(
            email="finance@example.com",
            password_hash="hashed",
            display_name="Finance",
            role=UserRole.finance,
            status=UserStatus.active,
        )
        provider = OcrProviderConfig(
            provider="tencent",
            display_name="Tencent OCR",
            enabled=True,
            is_default=True,
            credential_ciphertext={"alg": "fernet-sha256", "ciphertext": "token"},
            credential_fingerprint="sha256:test",
            quota_source=QuotaSource.manual,
        )
        project = Project(
            name="未分类",
            description="未指定项目的发票",
            visibility=ProjectVisibility.system,
            status=ProjectStatus.active,
            system_key="uncategorized",
        )
        document = InvoiceDocument(
            project=project,
            uploaded_by_user=user,
            original_filename="invoice.pdf",
            content_type="application/pdf",
            file_ext="pdf",
            file_size=1234,
            base64_size=1648,
            sha256="a" * 64,
            storage_key="2026/07/sample.pdf",
            page_count=1,
            status=DocumentStatus.ocr_done,
        )
        job = OcrJob(
            document=document,
            provider_config=provider,
            provider="tencent",
            endpoint="ocr.tencentcloudapi.com",
            action="VatInvoiceOCR",
            version="2018-11-19",
            status=OcrJobStatus.completed,
            idempotency_key="provider-action-page-sha",
            raw_response={"RequestId": "req-1"},
        )
        invoice = Invoice(
            document=document,
            latest_ocr_job=job,
            invoice_type="增值税电子普通发票",
            invoice_number="12345678",
            invoice_date=date(2026, 7, 9),
            seller_name="Seller Co",
            amount_with_tax=Decimal("128.50"),
            status=InvoiceStatus.needs_review,
            raw_ocr_payload={"RequestId": "req-1"},
        )
        item = InvoiceItem(invoice=invoice, name="Service", amount=Decimal("128.50"), raw_item_json={"Name": "Service"})
        export_task = ExportTask(format=ExportFormat.json, status=ExportStatus.queued, created_by_user=user)

        session.add_all([user, provider, project, document, job, invoice, item, export_task])
        session.commit()

        saved_invoice = session.get(Invoice, invoice.id)
        assert saved_invoice is not None
        assert saved_invoice.document.sha256 == "a" * 64
        assert saved_invoice.items[0].name == "Service"
        assert saved_invoice.latest_ocr_job.request_id is None
