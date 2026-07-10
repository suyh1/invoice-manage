import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


INITIAL_REVISION = "e5c7bce239f0"


def test_upgrade_backfills_existing_documents_to_uncategorized_project() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for migration integration test")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, INITIAL_REVISION)

    user_id = uuid4()
    document_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO users (id, email, password_hash, display_name, role, status)
                VALUES (:id, :email, :password_hash, :display_name, 'admin', 'active')
                """
            ),
            {
                "id": user_id,
                "email": "existing@example.com",
                "password_hash": "hashed",
                "display_name": "Existing Admin",
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO invoice_documents (
                    id, uploaded_by, original_filename, content_type, file_ext,
                    file_size, base64_size, sha256, storage_key, page_count, status
                ) VALUES (
                    :id, :uploaded_by, 'existing.pdf', 'application/pdf', 'pdf',
                    100, 136, :sha256, '2026/07/existing.pdf', 1, 'uploaded'
                )
                """
            ),
            {"id": document_id, "uploaded_by": user_id, "sha256": "a" * 64},
        )

    command.upgrade(config, "head")

    inspector = inspect(engine)
    assert "projects" in inspector.get_table_names()
    assert "system_state" in inspector.get_table_names()
    assert "session_version" in {column["name"] for column in inspector.get_columns("users")}
    assert "project_id" in {column["name"] for column in inspector.get_columns("invoice_documents")}
    assert "expense_scene" in {column["name"] for column in inspector.get_columns("invoice_documents")}
    assert "error_message" in {column["name"] for column in inspector.get_columns("export_tasks")}

    with engine.begin() as connection:
        project = connection.execute(
            text("SELECT id, name, visibility, status FROM projects WHERE system_key = 'uncategorized'")
        ).mappings().one()
        document_project_id = connection.execute(
            text("SELECT project_id FROM invoice_documents WHERE id = :id"), {"id": document_id}
        ).scalar_one()
        session_version = connection.execute(
            text("SELECT session_version FROM users WHERE id = :id"), {"id": user_id}
        ).scalar_one()
        state = connection.execute(text("SELECT initialized_at FROM system_state WHERE id = 1")).mappings().one()

    assert project["name"] == "未分类"
    assert project["visibility"] == "system"
    assert project["status"] == "active"
    assert document_project_id == project["id"]
    assert session_version == 1
    assert state["initialized_at"] is not None

    project_id_column = next(column for column in inspector.get_columns("invoice_documents") if column["name"] == "project_id")
    assert project_id_column["nullable"] is False
