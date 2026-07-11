from decimal import Decimal

from app.domain.project.models import ProjectVisibility
from app.domain.project.service import ProjectService
from app.domain.user.models import UserRole
from app.domain.user.service import create_session_token, create_user
from test_invoice_api import make_client, make_session, seed_invoice


def test_global_search_returns_grouped_invoice_project_and_supplier_matches() -> None:
    with make_session() as session:
        owner = create_user(
            session,
            email="owner@example.com",
            password="password",
            display_name="Owner",
            role=UserRole.user,
        )
        project = ProjectService().create_project(
            session,
            owner,
            {
                "name": "云栖差旅",
                "description": "上海酒店与交通发票",
                "visibility": ProjectVisibility.private.value,
            },
        )
        first = seed_invoice(
            session,
            user=owner,
            project=project,
            seller_name="上海云栖酒店",
            invoice_number="12876543",
        )
        seed_invoice(
            session,
            user=owner,
            project=project,
            seller_name="上海云栖酒店",
            invoice_number="12876544",
            amount_with_tax=Decimal("399.00"),
        )
        client = make_client(session)
        client.cookies.set("session", create_session_token(owner.id))

        response = client.get("/api/v1/search", params={"q": "云栖"})

        assert response.status_code == 200
        data = response.json()["data"]
        assert str(first.id) in {item["id"] for item in data["invoices"]}
        assert data["projects"] == [
            {
                "id": str(project.id),
                "name": "云栖差旅",
                "description": "上海酒店与交通发票",
            }
        ]
        assert data["suppliers"] == [{"name": "上海云栖酒店", "invoice_count": 2}]


def test_global_search_respects_invoice_and_project_visibility() -> None:
    with make_session() as session:
        owner = create_user(
            session,
            email="owner@example.com",
            password="password",
            display_name="Owner",
            role=UserRole.user,
        )
        other = create_user(
            session,
            email="other@example.com",
            password="password",
            display_name="Other",
            role=UserRole.user,
        )
        hidden_project = ProjectService().create_project(
            session,
            other,
            {
                "name": "机密采购",
                "description": "仅其他用户可见",
                "visibility": ProjectVisibility.private.value,
            },
        )
        seed_invoice(
            session,
            user=other,
            project=hidden_project,
            seller_name="机密供应商",
            invoice_number="99990000",
        )
        client = make_client(session)
        client.cookies.set("session", create_session_token(owner.id))

        response = client.get("/api/v1/search", params={"q": "机密"})

        assert response.status_code == 200
        assert response.json()["data"] == {"invoices": [], "projects": [], "suppliers": []}


def test_global_search_validates_query_and_applies_per_group_limit() -> None:
    with make_session() as session:
        owner = create_user(
            session,
            email="owner@example.com",
            password="password",
            display_name="Owner",
            role=UserRole.user,
        )
        seed_invoice(session, user=owner, seller_name="同名供应商", invoice_number="10000001")
        seed_invoice(session, user=owner, seller_name="同名供应商二店", invoice_number="10000002")
        client = make_client(session)
        client.cookies.set("session", create_session_token(owner.id))

        invalid = client.get("/api/v1/search", params={"q": "云"})
        limited = client.get("/api/v1/search", params={"q": "同名", "limit": 1})

        assert invalid.status_code == 422
        assert limited.status_code == 200
        assert len(limited.json()["data"]["invoices"]) == 1
        assert len(limited.json()["data"]["suppliers"]) == 1
