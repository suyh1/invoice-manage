"""make OCR jobs provider independent

Revision ID: a7c4d91e2b63
Revises: f4a8b2c19d70
Create Date: 2026-07-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c4d91e2b63"
down_revision: Union[str, Sequence[str], None] = "f4a8b2c19d70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("ocr_jobs") as batch_op:
        batch_op.drop_constraint(
            "fk_ocr_jobs_provider_config_id_ocr_provider_configs",
            type_="foreignkey",
        )
        batch_op.drop_column("provider_config_id")
        batch_op.alter_column("provider", existing_type=sa.String(length=40), nullable=True)
        batch_op.alter_column("endpoint", existing_type=sa.String(length=255), nullable=True)
        batch_op.alter_column("action", existing_type=sa.String(length=80), nullable=True)
        batch_op.alter_column("version", existing_type=sa.String(length=40), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("ocr_jobs") as batch_op:
        batch_op.add_column(sa.Column("provider_config_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_ocr_jobs_provider_config_id_ocr_provider_configs",
            "ocr_provider_configs",
            ["provider_config_id"],
            ["id"],
            ondelete="RESTRICT",
        )
