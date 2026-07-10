from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, import_all_models
from app.db.session import get_db
from app.domain.file.models import DocumentStatus, InvoiceDocument
from app.domain.invoice.duplicate import detect_duplicates_for_invoice
from app.domain.invoice.models import DuplicateCheck, DuplicateCheckStatus, Invoice, InvoiceStatus
from app.domain.project.service import ProjectService
from app.domain.user.models import UserRole
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
    invoice_code: str | None = "144032216011",
    invoice_number: str = "12876543",
    invoice_date: date = date(2026, 7, 9),
    seller_name: str = "上海云栖酒店",
    amount_with_tax: Decimal = Decimal("729.28"),
    status: InvoiceStatus = InvoiceStatus.needs_review,
) -> Invoice:
    document = InvoiceDocument(
        project=ProjectService().ensure_uncategorized(session),
        uploaded_by=user.id,
        original_filename=f"{invoice_number}.png",
        content_type="image/png",
        file_ext="png",
        file_size=100,
        base64_size=136,
        sha256=f"{invoice_number:0<64}"[:64],
        storage_key=f"2026/07/{invoice_number}.png",
        page_count=1,
        image_width=120,
        image_height=80,
        status=DocumentStatus.ocr_done,
    )
    invoice = Invoice(
        document=document,
        invoice_code=invoice_code,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        seller_name=seller_name,
        amount_with_tax=amount_with_tax,
        status=status,
    )
    session.add(invoice)
    session.commit()
    return invoice


def test_duplicate_detection_creates_strong_match_and_marks_invoice_suspected() -> None:
    with make_session() as session:
        user = create_user(session, email="user@example.com", password="password", display_name="User", role=UserRole.user)
        existing = seed_invoice(session, user=user)
        current = seed_invoice(session, user=user)

        checks = detect_duplicates_for_invoice(session, current)
        session.commit()

        assert len(checks) == 1
        assert checks[0].matched_invoice_id == existing.id
        assert checks[0].rule == "code_number_date_amount"
        assert checks[0].score == Decimal("1.0000")
        assert current.is_duplicate_suspected is True
        assert current.status == InvoiceStatus.duplicate_suspected


def test_duplicate_detection_creates_weak_and_electronic_matches() -> None:
    with make_session() as session:
        user = create_user(session, email="user@example.com", password="password", display_name="User", role=UserRole.user)
        weak_existing = seed_invoice(session, user=user, invoice_code="DIFFERENT")
        electronic_existing = seed_invoice(
            session,
            user=user,
            invoice_code=None,
            invoice_number="ELEC-001",
            seller_name="其他销售方",
        )
        weak_current = seed_invoice(session, user=user, invoice_code="CURRENT")
        electronic_current = seed_invoice(
            session,
            user=user,
            invoice_code=None,
            invoice_number="ELEC-001",
            seller_name="另一销售方",
        )

        weak_checks = detect_duplicates_for_invoice(session, weak_current)
        electronic_checks = detect_duplicates_for_invoice(session, electronic_current)

        assert [(check.matched_invoice_id, check.rule, check.score) for check in weak_checks] == [
            (weak_existing.id, "number_date_seller_amount", Decimal("0.8500"))
        ]
        assert [(check.matched_invoice_id, check.rule, check.score) for check in electronic_checks] == [
            (electronic_existing.id, "electronic_number_date_amount", Decimal("0.7000"))
        ]


def test_duplicate_detection_is_idempotent_for_same_invoice_pair() -> None:
    with make_session() as session:
        user = create_user(session, email="user@example.com", password="password", display_name="User", role=UserRole.user)
        seed_invoice(session, user=user)
        current = seed_invoice(session, user=user)

        detect_duplicates_for_invoice(session, current)
        detect_duplicates_for_invoice(session, current)
        session.commit()

        checks = session.scalars(select(DuplicateCheck).where(DuplicateCheck.invoice_id == current.id)).all()
        assert len(checks) == 1


def test_duplicate_check_apis_list_confirm_and_ignore() -> None:
    with make_session() as session:
        user = create_user(session, email="user@example.com", password="password", display_name="User", role=UserRole.user)
        finance = create_user(
            session, email="finance@example.com", password="password", display_name="Finance", role=UserRole.finance
        )
        existing = seed_invoice(session, user=user)
        current = seed_invoice(session, user=user)
        first_check = detect_duplicates_for_invoice(session, current)[0]
        second_check = DuplicateCheck(
            invoice=current,
            matched_invoice=existing,
            rule="manual_test",
            score=Decimal("0.5000"),
        )
        session.add(second_check)
        session.commit()
        client = make_client(session)
        client.cookies.set("session", create_session_token(finance.id))

        list_response = client.get(f"/api/v1/invoices/{current.id}/duplicate-checks")
        confirm_response = client.post(f"/api/v1/duplicate-checks/{first_check.id}/confirm")
        ignore_response = client.post(f"/api/v1/duplicate-checks/{second_check.id}/ignore")

        assert list_response.status_code == 200
        assert list_response.json()["data"][0]["matched_invoice_id"] == str(existing.id)
        assert confirm_response.status_code == 200
        assert confirm_response.json()["data"]["status"] == "confirmed_duplicate"
        assert ignore_response.status_code == 200
        assert ignore_response.json()["data"]["status"] == "ignored"
        assert session.get(DuplicateCheck, first_check.id).status == DuplicateCheckStatus.confirmed_duplicate
