from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.base import Base, import_all_models
from app.db.session import get_db
from app.domain.ocr.models import OcrProviderConfig, QuotaSource
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


def test_ordinary_user_can_read_normal_ocr_quota_status() -> None:
    with make_session() as session:
        user = create_user(
            session,
            email="user@example.com",
            password="password",
            display_name="User",
            role=UserRole.user,
        )
        provider = OcrProviderConfig(
            provider="tencent",
            display_name="Tencent OCR",
            enabled=True,
            is_default=True,
            quota_source=QuotaSource.manual,
            free_quota_total=1000,
            free_quota_used=250,
            quota_warning_percent=80,
            quota_warning_remaining=100,
        )
        session.add_all([user, provider])
        session.commit()
        client = make_client(session)
        client.cookies.set("session", create_session_token(user.id))

        response = client.get("/api/v1/ocr-quota/status")

        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "quota_total": 1000,
                "quota_used": 250,
                "used_percent": 25,
                "level": "none",
            }
        }


def test_ocr_quota_status_uses_configured_warning_threshold() -> None:
    with make_session() as session:
        user = create_user(
            session,
            email="finance@example.com",
            password="password",
            display_name="Finance",
            role=UserRole.finance,
        )
        provider = OcrProviderConfig(
            provider="tencent",
            display_name="Tencent OCR",
            enabled=True,
            is_default=True,
            quota_source=QuotaSource.manual,
            free_quota_total=1000,
            free_quota_used=800,
            quota_warning_percent=80,
            quota_warning_remaining=100,
        )
        session.add_all([user, provider])
        session.commit()
        client = make_client(session)
        client.cookies.set("session", create_session_token(user.id))

        response = client.get("/api/v1/ocr-quota/status")

        assert response.status_code == 200
        assert response.json()["data"]["level"] == "warning"
        assert response.json()["data"]["used_percent"] == 80


def test_ocr_quota_status_returns_empty_values_without_active_config() -> None:
    with make_session() as session:
        user = create_user(
            session,
            email="empty@example.com",
            password="password",
            display_name="Empty",
            role=UserRole.user,
        )
        session.commit()
        client = make_client(session)
        client.cookies.set("session", create_session_token(user.id))

        response = client.get("/api/v1/ocr-quota/status")

        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "quota_total": None,
                "quota_used": None,
                "used_percent": None,
                "level": "none",
            }
        }
