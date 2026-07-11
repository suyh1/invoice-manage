import io
import zipfile
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.documents import find_default_ocr_provider
from app.core.config import PROJECT_FILE_MAX_SIZE_BYTES, UPLOAD_VALIDATION_DEFAULTS, Settings
from app.db.base import Base, import_all_models
from app.db.session import get_db
from app.domain.file.models import DocumentKind, InvoiceDocument
from app.domain.file.storage import LocalFileStorage
from app.domain.file.validators import validate_project_file_upload, validate_upload
from app.domain.project.models import ProjectVisibility
from app.domain.project.service import ProjectService
from app.domain.user.models import AuditLog, User, UserRole
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


def make_ooxml_bytes(kind: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr(f"{kind}/document.xml" if kind == "word" else "xl/workbook.xml", "<root />")
    return output.getvalue()


@pytest.fixture()
def db_session() -> Session:
    import_all_models()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
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


def test_validate_upload_accepts_multi_page_pdf_for_page_number_recognition() -> None:
    validated = validate_upload("invoice.pdf", "application/pdf", make_pdf_bytes(2))

    assert validated.file_ext == "pdf"
    assert validated.page_count == 2


@pytest.mark.parametrize(
    ("filename", "content_type", "content", "expected_ext"),
    [
        ("receipt.pdf", "application/pdf", make_pdf_bytes(2), "pdf"),
        ("photo.png", "image/png", make_png_bytes(10, 10), "png"),
        ("photo.jpeg", "image/jpeg", make_jpeg_bytes(10, 10), "jpeg"),
        (
            "contract.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            make_ooxml_bytes("word"),
            "docx",
        ),
        (
            "records.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            make_ooxml_bytes("xl"),
            "xlsx",
        ),
    ],
)
def test_validate_project_file_accepts_business_formats(filename, content_type, content, expected_ext) -> None:
    validated = validate_project_file_upload(filename, content_type, content)

    assert validated.file_ext == expected_ext


def test_validate_project_file_rejects_mismatches_executables_and_files_over_50mb(monkeypatch) -> None:
    with pytest.raises(Exception) as mismatch:
        validate_project_file_upload("fake.docx", "application/octet-stream", make_ooxml_bytes("xl"))
    assert getattr(mismatch.value, "code") == "PROJECT_FILE_TYPE_MISMATCH"

    with pytest.raises(Exception) as executable:
        validate_project_file_upload("tool.exe", "application/octet-stream", b"MZ" + b"x" * 10)
    assert getattr(executable.value, "code") == "PROJECT_FILE_TYPE_UNSUPPORTED"

    assert PROJECT_FILE_MAX_SIZE_BYTES == 50 * 1024 * 1024
    monkeypatch.setattr("app.domain.file.validators.PROJECT_FILE_MAX_SIZE_BYTES", 100)
    with pytest.raises(Exception) as oversized:
        validate_project_file_upload("large.pdf", "application/pdf", make_pdf_bytes(1) + b"x" * 101)
    assert getattr(oversized.value, "code") == "PROJECT_FILE_TOO_LARGE"


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


def test_upload_document_queues_provider_independent_ocr_job_when_no_provider(
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

    monkeypatch.setattr("app.api.routes.documents.process_ocr_job_task.delay", lambda job_id: None)
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
    assert response.json()["data"]["ocr_job_id"] is not None
    assert response.json()["data"]["status"] == "ocr_queued"

    saved = db_session.query(InvoiceDocument).one()
    assert saved.uploaded_by == user.id
    assert saved.image_width == 120
    assert saved.image_height == 80
    assert saved.page_count == 1
    assert saved.status.value == "ocr_queued"
    assert saved.project.system_key == "uncategorized"
    assert (tmp_path / saved.storage_key).exists()
    audit = db_session.query(AuditLog).filter_by(action="document.upload").one()
    assert audit.actor_id == user.id
    assert audit.resource_type == "invoice_document"
    assert audit.resource_id == saved.id
    assert audit.audit_metadata["original_filename"] == "invoice.png"
    assert audit.audit_metadata["file_ext"] == "png"


def test_upload_document_assigns_visible_project_and_scene(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    owner = create_user(
        db_session,
        email="owner@example.com",
        password="password",
        display_name="Owner",
        role=UserRole.user,
    )
    other = create_user(
        db_session,
        email="other@example.com",
        password="password",
        display_name="Other",
        role=UserRole.user,
    )
    service = ProjectService()
    project = service.create_project(
        db_session,
        owner,
        {"name": "客户现场", "visibility": ProjectVisibility.private.value},
    )
    other_project = service.create_project(
        db_session,
        other,
        {"name": "他人项目", "visibility": ProjectVisibility.private.value},
    )
    db_session.commit()
    client.cookies.set("session", create_session_token(owner.id))
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

    uploaded = client.post(
        "/api/v1/documents",
        data={"auto_ocr": "false", "project_id": str(project.id), "scene": "travel"},
        files={"file": ("invoice.png", make_png_bytes(120, 80), "image/png")},
    )

    assert uploaded.status_code == 200
    saved = db_session.query(InvoiceDocument).one()
    assert saved.project_id == project.id
    assert saved.project.name == "客户现场"
    assert saved.expense_scene == "travel"

    forbidden = client.post(
        "/api/v1/documents",
        data={"auto_ocr": "false", "project_id": str(other_project.id)},
        files={"file": ("other.png", make_png_bytes(120, 80), "image/png")},
    )

    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "PROJECT_FORBIDDEN"


def test_upload_project_file_requires_project_and_never_creates_ocr(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    owner = create_user(
        db_session,
        email="project-file-owner@example.com",
        password="password",
        display_name="Project File Owner",
        role=UserRole.user,
    )
    project = ProjectService().create_project(
        db_session,
        owner,
        {"name": "车辆资料", "visibility": ProjectVisibility.private.value},
    )
    db_session.commit()
    client.cookies.set("session", create_session_token(owner.id))
    monkeypatch.setattr(
        "app.api.routes.documents.get_settings",
        lambda: Settings(
            _env_file=None,
            STORAGE_PATH=str(tmp_path),
            APP_SECRET_KEY="dev-secret-change-me",
            OCR_CONFIG_ENCRYPTION_KEY="dev-ocr-config-encryption-key-change-me",
        ),
    )

    missing_project = client.post(
        "/api/v1/documents",
        data={"document_kind": "project_file", "auto_ocr": "true"},
        files={"file": ("vehicle.docx", make_ooxml_bytes("word"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert missing_project.status_code == 400
    assert missing_project.json()["error"]["code"] == "PROJECT_FILE_PROJECT_REQUIRED"

    uploaded = client.post(
        "/api/v1/documents",
        data={
            "document_kind": "project_file",
            "auto_ocr": "true",
            "project_id": str(project.id),
            "scene": "travel",
        },
        files={"file": ("vehicle.docx", make_ooxml_bytes("word"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert uploaded.status_code == 200
    assert uploaded.json()["data"]["document_kind"] == "project_file"
    assert uploaded.json()["data"]["ocr_job_id"] is None
    saved = db_session.query(InvoiceDocument).one()
    assert saved.document_kind == DocumentKind.project_file
    assert saved.expense_scene is None
    assert saved.ocr_jobs == []


def test_document_preview_and_download_require_owner_access(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    owner = create_user(
        db_session,
        email="preview-owner@example.com",
        password="password",
        display_name="Preview Owner",
        role=UserRole.user,
    )
    other = create_user(
        db_session,
        email="preview-other@example.com",
        password="password",
        display_name="Preview Other",
        role=UserRole.user,
    )
    db_session.commit()
    settings = Settings(
        _env_file=None,
        STORAGE_PATH=str(tmp_path),
        APP_SECRET_KEY="dev-secret-change-me",
        OCR_CONFIG_ENCRYPTION_KEY="dev-ocr-config-encryption-key-change-me",
    )
    monkeypatch.setattr("app.api.routes.documents.get_settings", lambda: settings)
    client.cookies.set("session", create_session_token(owner.id))
    content = make_png_bytes(120, 80)

    uploaded = client.post(
        "/api/v1/documents",
        data={"auto_ocr": "false"},
        files={"file": ("invoice.png", content, "image/png")},
    )
    document_id = uploaded.json()["data"]["document_id"]

    preview = client.get(f"/api/v1/documents/{document_id}/preview")
    assert preview.status_code == 200
    assert preview.content == content
    assert preview.headers["content-type"] == "image/png"
    assert preview.headers["content-disposition"].startswith("inline;")

    download = client.get(f"/api/v1/documents/{document_id}/download")
    assert download.status_code == 200
    assert download.content == content
    assert download.headers["content-disposition"].startswith("attachment;")

    client.cookies.set("session", create_session_token(other.id))
    forbidden = client.get(f"/api/v1/documents/{document_id}/preview")
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "AUTH_FORBIDDEN"


def test_project_file_list_and_soft_delete_follow_document_permissions(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    finance = create_user(
        db_session,
        email="files-finance@example.com",
        password="password",
        display_name="Files Finance",
        role=UserRole.finance,
    )
    owner = create_user(
        db_session,
        email="files-owner@example.com",
        password="password",
        display_name="Files Owner",
        role=UserRole.user,
    )
    other = create_user(
        db_session,
        email="files-other@example.com",
        password="password",
        display_name="Files Other",
        role=UserRole.user,
    )
    project = ProjectService().create_project(
        db_session,
        finance,
        {"name": "共享车辆项目", "visibility": ProjectVisibility.shared.value},
    )
    db_session.commit()
    monkeypatch.setattr(
        "app.api.routes.documents.get_settings",
        lambda: Settings(
            _env_file=None,
            STORAGE_PATH=str(tmp_path),
            APP_SECRET_KEY="dev-secret-change-me",
            OCR_CONFIG_ENCRYPTION_KEY="dev-ocr-config-encryption-key-change-me",
        ),
    )

    def upload_as(user: User, filename: str, document_kind: str = "project_file") -> str:
        client.cookies.set("session", create_session_token(user.id))
        response = client.post(
            "/api/v1/documents",
            data={
                "document_kind": document_kind,
                "auto_ocr": "false",
                "project_id": str(project.id),
            },
            files={"file": (filename, make_pdf_bytes(1), "application/pdf")},
        )
        assert response.status_code == 200
        return response.json()["data"]["document_id"]

    owner_file_id = upload_as(owner, "owner-receipt.pdf")
    other_file_id = upload_as(other, "other-receipt.pdf")
    invoice_document_id = upload_as(owner, "invoice.pdf", "invoice")

    client.cookies.set("session", create_session_token(owner.id))
    owner_list = client.get(f"/api/v1/documents?document_kind=project_file&project_id={project.id}")
    assert owner_list.status_code == 200
    assert [item["id"] for item in owner_list.json()["data"]] == [owner_file_id]
    assert owner_list.json()["data"][0]["uploaded_by_user"]["display_name"] == "Files Owner"
    assert owner_list.json()["data"][0]["project"]["name"] == "共享车辆项目"

    forbidden_delete = client.delete(f"/api/v1/documents/{other_file_id}")
    assert forbidden_delete.status_code == 403
    assert forbidden_delete.json()["error"]["code"] == "AUTH_FORBIDDEN"

    invoice_delete = client.delete(f"/api/v1/documents/{invoice_document_id}")
    assert invoice_delete.status_code == 409
    assert invoice_delete.json()["error"]["code"] == "PROJECT_FILE_REQUIRED"

    deleted = client.delete(f"/api/v1/documents/{owner_file_id}")
    assert deleted.status_code == 200
    assert deleted.json()["data"] == {"ok": True}
    assert db_session.get(InvoiceDocument, UUID(owner_file_id)).status.value == "deleted"

    client.cookies.set("session", create_session_token(finance.id))
    finance_list = client.get(f"/api/v1/documents?document_kind=project_file&project_id={project.id}")
    assert finance_list.status_code == 200
    assert [item["id"] for item in finance_list.json()["data"]] == [other_file_id]
