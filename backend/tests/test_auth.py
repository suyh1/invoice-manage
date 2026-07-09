from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import assert_invoice_access, require_role
from app.cli import main as cli_main
from app.db.session import get_db
from app.domain.user.models import User, UserRole, UserStatus
from app.domain.user.service import create_user, verify_password
from app.main import create_app


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionLocal() as session:
        yield session


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_password_hash_round_trip_does_not_store_plaintext(db_session: Session) -> None:
    user = create_user(
        db_session,
        email="user@example.com",
        password="correct horse battery staple",
        display_name="User",
        role=UserRole.user,
    )

    assert "correct horse battery staple" not in user.password_hash
    assert user.password_hash.startswith("pbkdf2_sha256$")
    assert verify_password("correct horse battery staple", user.password_hash)
    assert not verify_password("wrong password", user.password_hash)


def test_login_me_and_logout_use_http_only_session_cookie(client: TestClient, db_session: Session) -> None:
    create_user(
        db_session,
        email="admin@example.com",
        password="admin-password",
        display_name="Admin",
        role=UserRole.admin,
    )

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin-password"},
    )

    assert login_response.status_code == 200
    assert login_response.json()["data"] == {
        "id": login_response.json()["data"]["id"],
        "email": "admin@example.com",
        "display_name": "Admin",
        "role": "admin",
    }
    assert "session=" in login_response.headers["set-cookie"]
    assert "HttpOnly" in login_response.headers["set-cookie"]
    assert "SameSite=Lax" in login_response.headers["set-cookie"]

    me_response = client.get("/api/v1/auth/me")

    assert me_response.status_code == 200
    assert me_response.json()["data"]["email"] == "admin@example.com"
    assert me_response.json()["data"]["role"] == "admin"

    logout_response = client.post("/api/v1/auth/logout")

    assert logout_response.status_code == 200
    assert "session=" in logout_response.headers["set-cookie"]
    assert "Max-Age=0" in logout_response.headers["set-cookie"]
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_rejects_wrong_password_and_disabled_users(client: TestClient, db_session: Session) -> None:
    create_user(
        db_session,
        email="disabled@example.com",
        password="disabled-password",
        display_name="Disabled",
        role=UserRole.user,
        status=UserStatus.disabled,
    )
    create_user(
        db_session,
        email="active@example.com",
        password="active-password",
        display_name="Active",
        role=UserRole.user,
    )

    wrong_password = client.post(
        "/api/v1/auth/login",
        json={"email": "active@example.com", "password": "wrong"},
    )
    disabled = client.post(
        "/api/v1/auth/login",
        json={"email": "disabled@example.com", "password": "disabled-password"},
    )

    assert wrong_password.status_code == 401
    assert wrong_password.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"
    assert disabled.status_code == 403
    assert disabled.json()["error"]["code"] == "AUTH_USER_DISABLED"


def test_role_dependency_allows_required_roles() -> None:
    finance_user = User(email="finance@example.com", password_hash="x", display_name="Finance", role=UserRole.finance)
    normal_user = User(email="user@example.com", password_hash="x", display_name="User", role=UserRole.user)

    assert require_role(UserRole.finance, UserRole.admin)(finance_user) is finance_user

    with pytest.raises(Exception) as exc_info:
        require_role(UserRole.finance, UserRole.admin)(normal_user)

    assert getattr(exc_info.value, "code") == "AUTH_FORBIDDEN"


def test_invoice_access_allows_owner_finance_and_admin_only() -> None:
    owner = User(id="owner-id", email="owner@example.com", password_hash="x", display_name="Owner", role=UserRole.user)
    other = User(id="other-id", email="other@example.com", password_hash="x", display_name="Other", role=UserRole.user)
    finance = User(
        id="finance-id", email="finance@example.com", password_hash="x", display_name="Finance", role=UserRole.finance
    )
    admin = User(id="admin-id", email="admin@example.com", password_hash="x", display_name="Admin", role=UserRole.admin)
    invoice = SimpleNamespace(document=SimpleNamespace(uploaded_by="owner-id"))

    assert assert_invoice_access(invoice, owner) is None
    assert assert_invoice_access(invoice, finance) is None
    assert assert_invoice_access(invoice, admin) is None

    with pytest.raises(Exception) as exc_info:
        assert_invoice_access(invoice, other)

    assert getattr(exc_info.value, "code") == "AUTH_FORBIDDEN"


def test_create_admin_cli_creates_admin_user(monkeypatch, db_session: Session, capsys) -> None:
    class SessionContext:
        def __enter__(self) -> Session:
            return db_session

        def __exit__(self, exc_type, exc, traceback) -> None:
            db_session.close()

    monkeypatch.setattr("app.cli.SessionLocal", SessionContext)
    monkeypatch.setattr(
        "sys.argv",
        [
            "invoice-app",
            "create-admin",
            "--email",
            "Admin@Example.com",
            "--password",
            "admin-password",
            "--display-name",
            "Admin User",
        ],
    )

    cli_main()

    saved = db_session.query(User).filter_by(email="admin@example.com").one()
    assert saved.role == UserRole.admin
    assert saved.display_name == "Admin User"
    assert verify_password("admin-password", saved.password_hash)
    assert "created admin user admin@example.com" in capsys.readouterr().out
