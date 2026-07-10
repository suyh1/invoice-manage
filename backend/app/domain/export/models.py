from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSON_VARIANT


class ExportFormat(str, enum.Enum):
    xlsx = "xlsx"
    csv = "csv"
    json = "json"
    zip = "zip"


class ExportStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class ExportTask(Base):
    __tablename__ = "export_tasks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    format: Mapped[ExportFormat] = mapped_column(
        Enum(ExportFormat, name="export_format", native_enum=False, create_constraint=True), nullable=False
    )
    filters: Mapped[dict[str, Any] | None] = mapped_column(JSON_VARIANT)
    status: Mapped[ExportStatus] = mapped_column(
        Enum(ExportStatus, name="export_status", native_enum=False, create_constraint=True),
        default=ExportStatus.queued,
        nullable=False,
    )
    storage_key: Mapped[str | None] = mapped_column(String(512))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by_user = relationship("User", back_populates="export_tasks")

    __table_args__ = (Index("ix_export_tasks_created_by_created_at", "created_by", "created_at"),)
