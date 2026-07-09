from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSON_VARIANT, TimestampMixin


class UserRole(str, enum.Enum):
    user = "user"
    finance = "finance"
    admin = "admin"


class UserStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False, create_constraint=True), nullable=False
    )
    department: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status", native_enum=False, create_constraint=True),
        default=UserStatus.active,
        nullable=False,
    )

    uploaded_documents = relationship("InvoiceDocument", back_populates="uploaded_by_user")
    configured_ocr_providers = relationship(
        "OcrProviderConfig", foreign_keys="OcrProviderConfig.created_by", back_populates="created_by_user"
    )
    export_tasks = relationship("ExportTask", back_populates="created_by_user")
    audit_logs = relationship("AuditLog", back_populates="actor")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_id: Mapped[UUID | None]
    audit_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON_VARIANT, default=dict, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    actor = relationship("User", back_populates="audit_logs")

    __table_args__ = (Index("ix_audit_logs_actor_id_created_at", "actor_id", "created_at"),)
