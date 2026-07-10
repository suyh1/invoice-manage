from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class ProjectVisibility(str, enum.Enum):
    private = "private"
    shared = "shared"
    system = "system"


class ProjectStatus(str, enum.Enum):
    active = "active"
    archived = "archived"


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[ProjectVisibility] = mapped_column(
        Enum(ProjectVisibility, name="project_visibility", native_enum=False, create_constraint=True),
        nullable=False,
    )
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status", native_enum=False, create_constraint=True),
        default=ProjectStatus.active,
        nullable=False,
    )
    system_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by_user = relationship("User", back_populates="projects")

    __table_args__ = (
        Index("ix_projects_visibility_status", "visibility", "status"),
        Index("ix_projects_created_by_status", "created_by", "status"),
    )
