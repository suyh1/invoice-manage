import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, import_all_models
from app.db.session import get_db
from app.domain.user.models import User, UserRole
from app.domain.user.service import create_session_token, create_user
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


def make_user(db: Session, email: str, role: UserRole) -> User:
    user = create_user(
        db,
        email=email,
        password="project-password-123",
        display_name=email.split("@", 1)[0],
        role=role,
    )
    db.commit()
    return user


def make_client(db: Session, user: User) -> TestClient:
    app = create_app()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    client.cookies.set("session", create_session_token(user.id, user.session_version))
    return client


def create_project(client: TestClient, name: str, visibility: str, description: str | None = None) -> dict:
    response = client.post(
        "/api/v1/projects",
        json={"name": name, "visibility": visibility, "description": description},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_normal_user_sees_system_shared_and_own_private_projects(db_session: Session) -> None:
    owner = make_user(db_session, "owner@example.com", UserRole.user)
    other = make_user(db_session, "other@example.com", UserRole.user)
    finance = make_user(db_session, "finance@example.com", UserRole.finance)
    owner_client = make_client(db_session, owner)
    other_client = make_client(db_session, other)
    finance_client = make_client(db_session, finance)

    create_project(finance_client, "共享差旅", "shared")
    create_project(owner_client, "我的采购", "private")
    create_project(other_client, "他人私有", "private")

    response = owner_client.get("/api/v1/projects")

    assert response.status_code == 200
    assert {project["name"] for project in response.json()["data"]} == {
        "未分类",
        "共享差旅",
        "我的采购",
    }
    uncategorized = next(project for project in response.json()["data"] if project["name"] == "未分类")
    assert uncategorized["visibility"] == "system"
    assert uncategorized["system_key"] == "uncategorized"
    assert uncategorized["can_manage"] is False


def test_normal_user_creates_private_but_not_shared_project(db_session: Session) -> None:
    user = make_user(db_session, "user@example.com", UserRole.user)
    client = make_client(db_session, user)

    created = create_project(client, "客户报销", "private", "客户现场费用")

    assert created["visibility"] == "private"
    assert created["created_by"] == str(user.id)
    assert created["can_manage"] is True

    forbidden = client.post(
        "/api/v1/projects",
        json={"name": "全员共享", "visibility": "shared"},
    )

    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "PROJECT_FORBIDDEN"


def test_finance_creates_and_manages_shared_project(db_session: Session) -> None:
    finance = make_user(db_session, "finance@example.com", UserRole.finance)
    client = make_client(db_session, finance)
    project = create_project(client, "年度审计", "shared")

    updated = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"name": "年度审计资料", "description": "财务共享"},
    )
    archived = client.post(f"/api/v1/projects/{project['id']}/archive")

    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "年度审计资料"
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived"
    assert all(item["id"] != project["id"] for item in client.get("/api/v1/projects").json()["data"])

    with_archived = client.get("/api/v1/projects?include_archived=true")
    archived_item = next(item for item in with_archived.json()["data"] if item["id"] == project["id"])
    assert archived_item["status"] == "archived"

    restored = client.post(f"/api/v1/projects/{project['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["data"]["status"] == "active"


def test_project_names_are_unique_in_their_scope(db_session: Session) -> None:
    first = make_user(db_session, "first@example.com", UserRole.user)
    second = make_user(db_session, "second@example.com", UserRole.user)
    finance = make_user(db_session, "finance@example.com", UserRole.finance)
    first_client = make_client(db_session, first)
    second_client = make_client(db_session, second)
    finance_client = make_client(db_session, finance)

    create_project(first_client, "差旅", "private")
    assert create_project(second_client, "差旅", "private")["name"] == "差旅"

    duplicate_private = first_client.post(
        "/api/v1/projects",
        json={"name": "差旅", "visibility": "private"},
    )
    create_project(finance_client, "公司采购", "shared")
    duplicate_shared = finance_client.post(
        "/api/v1/projects",
        json={"name": "公司采购", "visibility": "shared"},
    )

    assert duplicate_private.status_code == 409
    assert duplicate_private.json()["error"]["code"] == "PROJECT_NAME_EXISTS"
    assert duplicate_shared.status_code == 409
    assert duplicate_shared.json()["error"]["code"] == "PROJECT_NAME_EXISTS"


def test_system_project_is_immutable_and_private_projects_are_owner_managed(db_session: Session) -> None:
    owner = make_user(db_session, "owner@example.com", UserRole.user)
    other = make_user(db_session, "other@example.com", UserRole.user)
    owner_client = make_client(db_session, owner)
    other_client = make_client(db_session, other)
    private_project = create_project(owner_client, "我的项目", "private")
    uncategorized = next(
        item for item in owner_client.get("/api/v1/projects").json()["data"] if item["system_key"] == "uncategorized"
    )

    forbidden_private = other_client.patch(
        f"/api/v1/projects/{private_project['id']}",
        json={"name": "越权修改"},
    )
    immutable = owner_client.post(f"/api/v1/projects/{uncategorized['id']}/archive")

    assert forbidden_private.status_code == 403
    assert forbidden_private.json()["error"]["code"] == "PROJECT_FORBIDDEN"
    assert immutable.status_code == 409
    assert immutable.json()["error"]["code"] == "PROJECT_SYSTEM_IMMUTABLE"
