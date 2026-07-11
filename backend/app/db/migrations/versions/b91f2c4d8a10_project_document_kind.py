"""add project document kind

Revision ID: b91f2c4d8a10
Revises: a7c4d91e2b63
Create Date: 2026-07-11
"""

from alembic import op
import sqlalchemy as sa


revision = "b91f2c4d8a10"
down_revision = "a7c4d91e2b63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    document_kind = sa.Enum(
        "invoice",
        "project_file",
        name="document_kind",
        native_enum=False,
        create_constraint=True,
    )
    op.add_column(
        "invoice_documents",
        sa.Column(
            "document_kind",
            document_kind,
            server_default=sa.text("'invoice'"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_invoice_documents_project_kind_created_at",
        "invoice_documents",
        ["project_id", "document_kind", "created_at"],
        unique=False,
    )
    op.alter_column("invoice_documents", "document_kind", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_invoice_documents_project_kind_created_at", table_name="invoice_documents")
    op.drop_column("invoice_documents", "document_kind")
