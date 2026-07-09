from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, import_all_models
from app.db.session import get_db
from app.domain.file.models import DocumentStatus, InvoiceDocument
from app.domain.invoice.models import Invoice, InvoiceCorrection, InvoiceItem, InvoiceStatus
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


def make_client(session: Session) -> TestClient:
    app = create_app()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def seed_invoice(
    session: Session,
    *,
    user,
    original_filename: str = "invoice.png",
    file_ext: str = "png",
    status: InvoiceStatus = InvoiceStatus.needs_review,
    seller_name: str = "上海云栖酒店",
    buyer_name: str = "星河科技有限公司",
    invoice_number: str = "12876543",
    invoice_code: str = "144032216011",
    invoice_date: date = date(2026, 7, 9),
    amount_with_tax: Decimal = Decimal("729.28"),
    is_duplicate_suspected: bool = False,
) -> Invoice:
    provider = OcrProviderConfig(
        provider="tencent",
        display_name="Tencent OCR",
        enabled=True,
        is_default=False,
        quota_source=QuotaSource.manual,
    )
    document = InvoiceDocument(
        uploaded_by=user.id,
        original_filename=original_filename,
        content_type="image/png" if file_ext == "png" else "application/pdf",
        file_ext=file_ext,
        file_size=100,
        base64_size=136,
        sha256=f"{invoice_number:0<64}"[:64],
        storage_key=f"2026/07/{invoice_number}.{file_ext}",
        page_count=1,
        image_width=120 if file_ext == "png" else None,
        image_height=80 if file_ext == "png" else None,
        status=DocumentStatus.ocr_done,
        created_at=datetime(2026, 7, 9, 9, 0, tzinfo=UTC),
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
        idempotency_key=f"job-{invoice_number}",
        request_id=f"req-{invoice_number}",
        raw_response={"RequestId": f"req-{invoice_number}"},
        raw_request_meta={"duration_ms": 123},
        finished_at=datetime(2026, 7, 9, 9, 1, tzinfo=UTC),
    )
    invoice = Invoice(
        document=document,
        latest_ocr_job=job,
        invoice_type="增值税电子普通发票",
        invoice_code=invoice_code,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        seller_name=seller_name,
        seller_tax_id="91310000MA1K000002",
        buyer_name=buyer_name,
        buyer_tax_id="91310000MA1K000001",
        amount_without_tax=Decimal("688.00"),
        tax_amount=Decimal("41.28"),
        amount_with_tax=amount_with_tax,
        check_code="12345678901234567890",
        currency="CNY",
        expense_scene="travel",
        status=status,
        is_duplicate_suspected=is_duplicate_suspected,
        raw_ocr_payload={"RequestId": f"req-{invoice_number}"},
        normalized_payload={
            "invoice_fields": {
                "seller_name": seller_name,
                "amount_with_tax": str(amount_with_tax),
            }
        },
    )
    invoice.items.append(
        InvoiceItem(
            name="住宿服务",
            specification="标准间",
            unit="晚",
            quantity=Decimal("1.0000"),
            unit_price=Decimal("688.0000"),
            amount=Decimal("688.00"),
            tax_rate=Decimal("0.0600"),
            tax_amount=Decimal("41.28"),
            raw_item_json={"Name": "住宿服务"},
        )
    )
    invoice.corrections.append(
        InvoiceCorrection(
            field_path="seller_name",
            ocr_value="上海云栖酒店",
            old_value="上海云栖酒店",
            new_value=seller_name,
            changed_by=user.id,
        )
    )
    session.add(invoice)
    session.commit()
    return invoice


def test_invoice_list_filters_and_limits_normal_user_to_owned_invoices() -> None:
    with make_session() as session:
        owner = create_user(session, email="owner@example.com", password="password", display_name="Owner", role=UserRole.user)
        other = create_user(session, email="other@example.com", password="password", display_name="Other", role=UserRole.user)
        wanted = seed_invoice(session, user=owner)
        seed_invoice(
            session,
            user=owner,
            status=InvoiceStatus.confirmed,
            seller_name="办公用品商店",
            invoice_number="55550000",
            amount_with_tax=Decimal("50.00"),
            is_duplicate_suspected=True,
            file_ext="pdf",
        )
        seed_invoice(session, user=other, invoice_number="99990000", seller_name="上海云栖酒店")
        client = make_client(session)
        client.cookies.set("session", create_session_token(owner.id))

        response = client.get(
            "/api/v1/invoices",
            params={
                "status": "needs_review",
                "invoice_date_from": "2026-07-01",
                "invoice_date_to": "2026-07-31",
                "amount_min": "700",
                "amount_max": "800",
                "seller_name": "云栖",
                "buyer_name": "星河",
                "invoice_number": "1287",
                "invoice_code": "144032",
                "file_type": "png",
                "duplicate": "false",
                "q": "酒店",
            },
        )

        assert response.status_code == 200
        assert response.json()["data"]["total"] == 1
        assert response.json()["data"]["items"][0]["id"] == str(wanted.id)
        assert response.json()["data"]["items"][0]["amount_with_tax"] == "729.28"


def test_invoice_detail_includes_document_ocr_items_and_corrections() -> None:
    with make_session() as session:
        owner = create_user(session, email="owner@example.com", password="password", display_name="Owner", role=UserRole.user)
        finance = create_user(
            session, email="finance@example.com", password="password", display_name="Finance", role=UserRole.finance
        )
        invoice = seed_invoice(session, user=owner)
        client = make_client(session)
        client.cookies.set("session", create_session_token(finance.id))

        response = client.get(f"/api/v1/invoices/{invoice.id}")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["id"] == str(invoice.id)
        assert data["document"]["original_filename"] == "invoice.png"
        assert data["ocr"]["request_id"] == "req-12876543"
        assert data["items"][0]["name"] == "住宿服务"
        assert data["items"][0]["tax_rate"] == "0.0600"
        assert data["corrections"][0]["field_path"] == "seller_name"


def test_invoice_patch_updates_fields_and_logs_corrections() -> None:
    with make_session() as session:
        owner = create_user(session, email="owner@example.com", password="password", display_name="Owner", role=UserRole.user)
        invoice = seed_invoice(session, user=owner)
        client = make_client(session)
        client.cookies.set("session", create_session_token(owner.id))

        response = client.patch(
            f"/api/v1/invoices/{invoice.id}",
            json={"seller_name": "上海云栖酒店管理有限公司", "amount_with_tax": "730.00"},
        )

        assert response.status_code == 200
        assert response.json()["data"]["seller_name"] == "上海云栖酒店管理有限公司"
        assert response.json()["data"]["amount_with_tax"] == "730.00"

        corrections = session.scalars(select(InvoiceCorrection).where(InvoiceCorrection.invoice_id == invoice.id)).all()
        assert [(correction.field_path, correction.ocr_value, correction.old_value, correction.new_value) for correction in corrections[-2:]] == [
            ("seller_name", "上海云栖酒店", "上海云栖酒店", "上海云栖酒店管理有限公司"),
            ("amount_with_tax", "729.28", "729.28", "730.00"),
        ]
        audit = session.scalar(select(AuditLog).where(AuditLog.action == "invoice.correct"))
        assert audit is not None
        assert audit.actor_id == owner.id
        assert audit.resource_type == "invoice"
        assert audit.resource_id == invoice.id
        assert audit.audit_metadata["fields"] == ["seller_name", "amount_with_tax"]


def test_invoice_confirm_archive_and_soft_delete() -> None:
    with make_session() as session:
        owner = create_user(session, email="owner@example.com", password="password", display_name="Owner", role=UserRole.user)
        invoice = seed_invoice(session, user=owner)
        client = make_client(session)
        client.cookies.set("session", create_session_token(owner.id))

        confirm = client.post(f"/api/v1/invoices/{invoice.id}/confirm")
        archive = client.post(f"/api/v1/invoices/{invoice.id}/archive")
        delete = client.delete(f"/api/v1/invoices/{invoice.id}")

        assert confirm.status_code == 200
        assert confirm.json()["data"]["status"] == "confirmed"
        assert archive.status_code == 200
        assert archive.json()["data"]["status"] == "archived"
        assert delete.status_code == 200
        assert delete.json()["data"]["status"] == "deleted"
        assert session.get(Invoice, invoice.id).status == InvoiceStatus.deleted


def test_invoice_api_denies_normal_user_access_to_other_users_invoice() -> None:
    with make_session() as session:
        owner = create_user(session, email="owner@example.com", password="password", display_name="Owner", role=UserRole.user)
        other = create_user(session, email="other@example.com", password="password", display_name="Other", role=UserRole.user)
        finance = create_user(
            session, email="finance@example.com", password="password", display_name="Finance", role=UserRole.finance
        )
        invoice = seed_invoice(session, user=owner)
        client = make_client(session)

        client.cookies.set("session", create_session_token(other.id))
        forbidden = client.get(f"/api/v1/invoices/{invoice.id}")
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "AUTH_FORBIDDEN"

        client.cookies.set("session", create_session_token(finance.id))
        allowed = client.get(f"/api/v1/invoices/{invoice.id}")
        assert allowed.status_code == 200
