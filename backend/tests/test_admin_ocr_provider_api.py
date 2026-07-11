from uuid import UUID

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.base import Base, import_all_models
from app.db.session import get_db
from app.domain.ocr.models import OcrProviderConfig, QuotaSource
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
        create_audit = session.scalar(select(AuditLog).where(AuditLog.action == "ocr_provider.create"))
        assert create_audit is not None
        assert create_audit.actor_id == admin.id
        assert create_audit.resource_type == "ocr_provider_config"
        assert create_audit.resource_id == UUID(provider_id)
        assert "AKID" not in str(create_audit.audit_metadata)
        assert "SECRET" not in str(create_audit.audit_metadata)

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
        quota_audit = session.scalar(select(AuditLog).where(AuditLog.action == "ocr_provider.quota_calibrate"))
        assert quota_audit is not None
        assert quota_audit.resource_id == UUID(provider_id)
        assert quota_audit.audit_metadata["free_quota_used"] == 950

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
        session.refresh(first)
        session.refresh(second)
        assert first.enabled is False
        assert first.is_default is False
        assert second.enabled is True
        assert second.is_default is True

        rotate_response = client.post(
            f"/api/v1/admin/ocr-providers/{first.id}/rotate-credential",
            json={"secret_id": "AKID2", "secret_key": "SECRET2"},
        )
        assert rotate_response.status_code == 200
        assert rotate_response.json()["data"]["configured"] is True
        default_audit = session.scalar(select(AuditLog).where(AuditLog.action == "ocr_provider.set_default"))
        assert default_audit is not None
        assert default_audit.resource_id == second.id
        rotate_audit = session.scalar(select(AuditLog).where(AuditLog.action == "ocr_provider.credential_rotate"))
        assert rotate_audit is not None
        assert rotate_audit.resource_id == first.id
        assert "AKID2" not in str(rotate_audit.audit_metadata)
        assert "SECRET2" not in str(rotate_audit.audit_metadata)


def test_admin_can_delete_provider_config_directly() -> None:
    with make_session() as session:
        admin = create_user(
            session,
            email="delete-admin@example.com",
            password="password",
            display_name="Delete Admin",
            role=UserRole.admin,
        )
        provider = OcrProviderConfig(
            provider="mock",
            display_name="Disposable OCR",
            enabled=True,
            is_default=True,
            quota_source=QuotaSource.manual,
        )
        session.add_all([admin, provider])
        session.commit()
        provider_id = provider.id
        client = make_client(session)
        client.cookies.set("session", create_session_token(admin.id))

        response = client.delete(f"/api/v1/admin/ocr-providers/{provider_id}")

        assert response.status_code == 200
        assert response.json()["data"]["deleted"] is True
        assert session.get(OcrProviderConfig, provider_id) is None


def test_admin_cannot_save_used_quota_greater_than_total() -> None:
    with make_session() as session:
        admin = create_user(
            session,
            email="quota-admin@example.com",
            password="password",
            display_name="Quota Admin",
            role=UserRole.admin,
        )
        session.commit()
        client = make_client(session)
        client.cookies.set("session", create_session_token(admin.id))

        response = client.post(
            "/api/v1/admin/ocr-providers",
            json={
                "provider": "mock",
                "display_name": "Mock OCR",
                "enabled": True,
                "is_default": True,
                "quota": {
                    "source": "manual",
                    "free_quota_total": 4,
                    "free_quota_used": 1000,
                    "quota_warning_percent": 80,
                    "quota_warning_remaining": 100,
                },
            },
        )

        assert response.status_code == 422
