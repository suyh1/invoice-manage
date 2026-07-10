"""user projects workflows

Revision ID: f4a8b2c19d70
Revises: e5c7bce239f0
Create Date: 2026-07-10 12:00:00+00:00
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "f4a8b2c19d70"
down_revision = "e5c7bce239f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )

    op.create_table(
        "system_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("initialized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("initialized_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["initialized_by"],
            ["users.id"],
            name=op.f("fk_system_state_initialized_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_system_state")),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "visibility",
            sa.Enum("private", "shared", "system", name="project_visibility", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("active", "archived", name="project_status", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("system_key", sa.String(length=80), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_projects_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
        sa.UniqueConstraint("system_key", name=op.f("uq_projects_system_key")),
    )
    op.create_index("ix_projects_visibility_status", "projects", ["visibility", "status"], unique=False)
    op.create_index("ix_projects_created_by_status", "projects", ["created_by", "status"], unique=False)
    op.create_index(
        "uq_projects_shared_name",
        "projects",
        [sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("visibility = 'shared'"),
    )
    op.create_index(
        "uq_projects_private_owner_name",
        "projects",
        ["created_by", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("visibility = 'private'"),
    )

    uncategorized_id = uuid4()
    projects = sa.table(
        "projects",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("visibility", sa.String()),
        sa.column("status", sa.String()),
        sa.column("system_key", sa.String()),
    )
    op.bulk_insert(
        projects,
        [
            {
                "id": uncategorized_id,
                "name": "未分类",
                "description": "未指定项目的发票",
                "visibility": "system",
                "status": "active",
                "system_key": "uncategorized",
            }
        ],
    )

    op.add_column("invoice_documents", sa.Column("project_id", sa.Uuid(), nullable=True))
    op.add_column("invoice_documents", sa.Column("expense_scene", sa.String(length=80), nullable=True))
    op.execute(
        sa.text("UPDATE invoice_documents SET project_id = :project_id").bindparams(project_id=uncategorized_id)
    )
    op.alter_column("invoice_documents", "project_id", existing_type=sa.Uuid(), nullable=False)
    op.create_foreign_key(
        op.f("fk_invoice_documents_project_id_projects"),
        "invoice_documents",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_invoice_documents_project_id_created_at",
        "invoice_documents",
        ["project_id", "created_at"],
        unique=False,
    )

    op.add_column("export_tasks", sa.Column("error_message", sa.String(length=1000), nullable=True))

    op.execute(sa.text("INSERT INTO system_state (id) VALUES (1)"))
    op.execute(
        sa.text(
            """
            UPDATE system_state
            SET initialized_at = now(),
                initialized_by = (SELECT id FROM users ORDER BY created_at ASC, id ASC LIMIT 1)
            WHERE id = 1 AND EXISTS (SELECT 1 FROM users)
            """
        )
    )
    op.alter_column("users", "session_version", server_default=None)


def downgrade() -> None:
    op.drop_column("export_tasks", "error_message")
    op.drop_index("ix_invoice_documents_project_id_created_at", table_name="invoice_documents")
    op.drop_constraint(
        op.f("fk_invoice_documents_project_id_projects"),
        "invoice_documents",
        type_="foreignkey",
    )
    op.drop_column("invoice_documents", "expense_scene")
    op.drop_column("invoice_documents", "project_id")
    op.drop_index("uq_projects_private_owner_name", table_name="projects")
    op.drop_index("uq_projects_shared_name", table_name="projects")
    op.drop_index("ix_projects_created_by_status", table_name="projects")
    op.drop_index("ix_projects_visibility_status", table_name="projects")
    op.drop_table("projects")
    op.drop_table("system_state")
    op.drop_column("users", "session_version")
