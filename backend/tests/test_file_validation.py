from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.documents import find_default_ocr_provider
from app.core.config import UPLOAD_VALIDATION_DEFAULTS, Settings
from app.db.base import import_all_models
from app.db.session import get_db
from app.domain.file.models import InvoiceDocument
from app.domain.file.storage import LocalFileStorage
from app.domain.file.validators import validate_upload
from app.domain.user.models import User, UserRole
from app.domain.user.service import create_session_token, create_user
from app.main import create_app


def make_png_bytes(width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )


def make_jpeg_bytes(width: int, height: int) -> bytes:
    return (
        b"\xff\xd8"
        + b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        + b"\xff\xc0\x00\x11\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01"
        + b"\xff\xd9"
    )


def make_gif_bytes(width: int, height: int) -> bytes:
    return b"GIF89a" + width.to_bytes(2, "little") + height.to_bytes(2, "little") + b"\x80\x00\x00"


def make_pdf_bytes(page_count: int) -> bytes:
    page_objects = []
    kids = []
    object_number = 3
    for _ in range(page_count):
        kids.append(f"{object_number} 0 R".encode("ascii"))
        page_objects.append(
            f"{object_number} 0 obj\n<< /Type /Page /Parent 2 0 R >>\nendobj\n".encode("ascii")
        )
        object_number += 1
    return (
        b"%PDF-1.4\n"
        + b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        + f"2 0 obj\n<< /Type /Pages /Kids [{' '.join(k.decode('ascii') for k in kids)}] /Count {page_count} >>\nendobj\n".encode(
            "ascii"
        )
        + b"".join(page_objects)
        + b"%%EOF\n"
    )


@pytest.fixture()
def db_session() -> Session:
    import_all_models()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(engine)
    InvoiceDocument.__table__.create(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_local() as session:
        yield session


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_validate_upload_accepts_png_and_extracts_dimensions() -> None:
    validated = validate_upload("invoice.png", "image/png", make_png_bytes(120, 80))

    assert validated.file_ext == "png"
    assert validated.image_width == 120
    assert validated.image_height == 80
    assert validated.page_count == 1
    assert validated.base64_size == 44


def test_validate_upload_accepts_jpeg_magic_bytes() -> None:
    validated = validate_upload("invoice.jpg", "image/jpeg", make_jpeg_bytes(240, 180))

    assert validated.file_ext == "jpg"
    assert validated.image_width == 240
    assert validated.image_height == 180


def test_validate_upload_rejects_gif_files() -> None:
    with pytest.raises(Exception) as exc_info:
        validate_upload("invoice.gif", "image/gif", make_gif_bytes(120, 80))

    assert getattr(exc_info.value, "code") == "OCR_GIF_NOT_SUPPORTED"


def test_validate_upload_rejects_files_over_base64_limit() -> None:
    oversized = make_pdf_bytes(1) + b"a" * (3 * (UPLOAD_VALIDATION_DEFAULTS.max_base64_size_bytes // 4) + 1)

    with pytest.raises(Exception) as exc_info:
        validate_upload("invoice.pdf", "application/pdf", oversized)

    assert getattr(exc_info.value, "code") == "OCR_FILE_TOO_LARGE"


def test_validate_upload_rejects_small_image_dimensions() -> None:
    with pytest.raises(Exception) as exc_info:
        validate_upload("invoice.png", "image/png", make_png_bytes(10, 10))

    assert getattr(exc_info.value, "code") == "OCR_INVALID_IMAGE_SIZE"


def test_validate_upload_rejects_multi_page_pdf() -> None:
    with pytest.raises(Exception) as exc_info:
        validate_upload("invoice.pdf", "application/pdf", make_pdf_bytes(2))

    assert getattr(exc_info.value, "code") == "OCR_PDF_MULTI_PAGE_NOT_SUPPORTED"


def test_local_file_storage_writes_under_year_month_and_sha(tmp_path) -> None:
    validated = validate_upload("invoice.png", "image/png", make_png_bytes(120, 80))
    storage = LocalFileStorage(tmp_path)

    storage_key = storage.save(
        validated,
        created_at=datetime(2026, 7, 9, 12, 0, tzinfo=UTC),
    )

    assert storage_key == "2026/07/{}".format(f"{validated.sha256}.png")
    assert (tmp_path / storage_key).read_bytes() == validated.content


def test_upload_document_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("invoice.png", make_png_bytes(120, 80), "image/png")},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_upload_document_creates_document_without_ocr_job_when_no_provider(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    user = create_user(
        db_session,
        email="user@example.com",
        password="password",
        display_name="User",
        role=UserRole.user,
    )
    db_session.commit()
    client.cookies.set("session", create_session_token(user.id))

    monkeypatch.setattr("app.api.routes.documents.find_default_ocr_provider", lambda db: None)
    monkeypatch.setattr(
        "app.api.routes.documents.get_settings",
        lambda: Settings(
            _env_file=None,
            STORAGE_PATH=str(tmp_path),
            APP_SECRET_KEY="dev-secret-change-me",
            OCR_CONFIG_ENCRYPTION_KEY="dev-ocr-config-encryption-key-change-me",
        ),
    )

    response = client.post(
        "/api/v1/documents",
        data={"auto_ocr": "true"},
        files={"file": ("invoice.png", make_png_bytes(120, 80), "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["data"]["ocr_job_id"] is None
    assert response.json()["data"]["status"] == "uploaded"

    saved = db_session.query(InvoiceDocument).one()
    assert saved.uploaded_by == user.id
    assert saved.image_width == 120
    assert saved.image_height == 80
    assert saved.page_count == 1
    assert saved.status.value == "uploaded"
    assert (tmp_path / saved.storage_key).exists()
