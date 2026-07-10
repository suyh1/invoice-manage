import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, import_all_models
from app.db.session import get_db
from app.domain.user.models import AuditLog, User, UserRole, UserStatus
from app.domain.user.service import create_session_token, create_user, verify_password
from app.main import create_app


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


def make_client(db_session: Session, user: User) -> TestClient:
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    client.cookies.set("session", create_session_token(user.id, user.session_version))
    return client


def create_admin(db_session: Session, email: str = "admin@example.com") -> User:
    user = create_user(
        db_session,
        email=email,
        password="admin-password-123",
        display_name="Administrator",
        role=UserRole.admin,
    )
    db_session.commit()
    return user


def test_admin_lists_and_creates_user_with_default_role(db_session: Session) -> None:
    admin = create_admin(db_session)
    client = make_client(db_session, admin)

    created = client.post(
        "/api/v1/admin/users",
        json={
            "email": "Member@Example.com",
            "password": "member-password-123",
            "display_name": "Member",
            "department": "Operations",
        },
    )

    assert created.status_code == 200
    assert {
        "email": "member@example.com",
        "display_name": "Member",
        "department": "Operations",
        "role": "user",
        "status": "active",
    }.items() <= created.json()["data"].items()
    saved = db_session.query(User).filter_by(email="member@example.com").one()
    assert saved.role == UserRole.user
    assert verify_password("member-password-123", saved.password_hash)

    listed = client.get("/api/v1/admin/users")

    assert listed.status_code == 200
    assert {item["email"] for item in listed.json()["data"]} == {
        "admin@example.com",
        "member@example.com",
    }
    audit = db_session.query(AuditLog).filter_by(action="user.create").one()
    assert audit.actor_id == admin.id
    assert audit.resource_id == saved.id
    assert "member-password-123" not in str(audit.audit_metadata)


def test_normal_user_cannot_manage_users(db_session: Session) -> None:
    normal = create_user(
        db_session,
        email="user@example.com",
        password="user-password-123",
        display_name="User",
        role=UserRole.user,
    )
    db_session.commit()
    client = make_client(db_session, normal)

    assert client.get("/api/v1/admin/users").status_code == 403
    assert client.post(
        "/api/v1/admin/users",
        json={
            "email": "other@example.com",
            "password": "other-password-123",
            "display_name": "Other",
        },
    ).status_code == 403


def test_admin_updates_user_and_resets_password(db_session: Session) -> None:
    admin = create_admin(db_session)
    member = create_user(
        db_session,
        email="member@example.com",
        password="old-member-password",
        display_name="Member",
        role=UserRole.user,
    )
    db_session.commit()
    client = make_client(db_session, admin)

    updated = client.patch(
        f"/api/v1/admin/users/{member.id}",
        json={
            "display_name": "Finance Member",
            "department": "Finance",
            "role": "finance",
        },
    )

    assert updated.status_code == 200
    assert updated.json()["data"]["display_name"] == "Finance Member"
    assert updated.json()["data"]["department"] == "Finance"
    assert updated.json()["data"]["role"] == "finance"

    reset = client.post(
        f"/api/v1/admin/users/{member.id}/reset-password",
        json={"password": "new-member-password"},
    )

    assert reset.status_code == 200
    db_session.refresh(member)
    assert member.session_version == 2
    assert verify_password("new-member-password", member.password_hash)
    assert not verify_password("old-member-password", member.password_hash)
    actions = {audit.action for audit in db_session.query(AuditLog).filter(AuditLog.resource_id == member.id).all()}
    assert {"user.update", "user.password_reset"}.issubset(actions)


@pytest.mark.parametrize("payload", [{"role": "user"}, {"status": "disabled"}])
def test_last_active_admin_cannot_be_demoted_or_disabled(db_session: Session, payload: dict[str, str]) -> None:
    admin = create_admin(db_session)
    client = make_client(db_session, admin)

    response = client.patch(f"/api/v1/admin/users/{admin.id}", json=payload)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AUTH_LAST_ADMIN_REQUIRED"
    db_session.refresh(admin)
    assert admin.role == UserRole.admin
    assert admin.status == UserStatus.active


def test_duplicate_user_email_is_rejected(db_session: Session) -> None:
    admin = create_admin(db_session)
    create_user(
        db_session,
        email="member@example.com",
        password="member-password-123",
        display_name="Member",
        role=UserRole.user,
    )
    db_session.commit()
    client = make_client(db_session, admin)

    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": "MEMBER@example.com",
            "password": "different-password",
            "display_name": "Duplicate",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USER_EMAIL_EXISTS"
    assert db_session.query(User).filter_by(email="member@example.com").count() == 1
