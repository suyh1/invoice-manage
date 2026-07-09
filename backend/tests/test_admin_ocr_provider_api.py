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


def test_admin_ocr_api_requires_admin_role() -> None:
    with make_session() as session:
        user = create_user(
            session,
            email="user@example.com",
            password="password",
            display_name="User",
            role=UserRole.user,
        )
        session.commit()
        client = make_client(session)
        client.cookies.set("session", create_session_token(user.id))

        response = client.get("/api/v1/admin/ocr-providers")

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "AUTH_FORBIDDEN"


def test_admin_can_create_list_test_and_calibrate_provider(monkeypatch) -> None:
    with make_session() as session:
        admin = create_user(
            session,
            email="admin@example.com",
            password="password",
            display_name="Admin",
            role=UserRole.admin,
        )
        session.commit()
        client = make_client(session)
        client.cookies.set("session", create_session_token(admin.id))

        class FakeClient:
            def test_connection(self, provider, credential):
                return {"ok": True, "message": "connected"}

        class FakeRegistry:
            def get_client(self, provider_name: str):
                return FakeClient()

        monkeypatch.setattr("app.api.routes.admin_ocr.get_registry", lambda: FakeRegistry())

        create_response = client.post(
            "/api/v1/admin/ocr-providers",
            json={
                "provider": "tencent",
                "display_name": "Tencent OCR",
                "enabled": True,
                "is_default": True,
                "credential": {"secret_id": "AKID", "secret_key": "SECRET"},
                "quota": {
                    "source": "manual",
                    "free_quota_total": 1000,
                    "free_quota_used": 120,
                    "quota_warning_percent": 80,
                    "quota_warning_remaining": 100
                }
            },
        )

        assert create_response.status_code == 200
        provider_id = create_response.json()["data"]["id"]

        list_response = client.get("/api/v1/admin/ocr-providers")
        assert list_response.status_code == 200
        assert list_response.json()["data"][0]["configured"] is True
        assert "credential" not in list_response.json()["data"][0]

        test_response = client.post(f"/api/v1/admin/ocr-providers/{provider_id}/test")
        assert test_response.status_code == 200
        assert test_response.json()["data"]["status"] == "success"

        calibration_response = client.post(
            f"/api/v1/admin/ocr-providers/{provider_id}/quota-calibration",
            json={
                "free_quota_total": 1000,
                "free_quota_used": 950,
                "quota_reset_at": "2026-08-01T00:00:00+08:00",
                "note": "manual calibration"
            },
        )
        assert calibration_response.status_code == 200
        assert calibration_response.json()["data"]["quota"]["free_quota_used"] == 950

        alerts_response = client.get("/api/v1/admin/ocr-quota-alerts")
        assert alerts_response.status_code == 200
        assert alerts_response.json()["data"][0]["status"] == "active"

        alert_id = alerts_response.json()["data"][0]["id"]
        acknowledge_response = client.post(f"/api/v1/admin/ocr-quota-alerts/{alert_id}/acknowledge")
        assert acknowledge_response.status_code == 200
        assert acknowledge_response.json()["data"]["status"] == "acknowledged"


def test_admin_can_switch_default_provider_and_rotate_credentials() -> None:
    with make_session() as session:
        admin = create_user(
            session,
            email="admin@example.com",
            password="password",
            display_name="Admin",
            role=UserRole.admin,
        )
        first = OcrProviderConfig(
            provider="tencent",
            display_name="Tencent OCR",
            enabled=True,
            is_default=True,
            quota_source=QuotaSource.manual,
        )
        second = OcrProviderConfig(
            provider="mock",
            display_name="Mock OCR",
            enabled=True,
            is_default=False,
            quota_source=QuotaSource.manual,
        )
        session.add_all([admin, first, second])
        session.commit()
        client = make_client(session)
        client.cookies.set("session", create_session_token(admin.id))

        set_default_response = client.post(f"/api/v1/admin/ocr-providers/{second.id}/set-default")
        assert set_default_response.status_code == 200

        rotate_response = client.post(
            f"/api/v1/admin/ocr-providers/{first.id}/rotate-credential",
            json={"secret_id": "AKID2", "secret_key": "SECRET2"},
        )
        assert rotate_response.status_code == 200
        assert rotate_response.json()["data"]["configured"] is True
