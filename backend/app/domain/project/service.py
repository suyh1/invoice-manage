from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domain.project.models import Project, ProjectStatus, ProjectVisibility
from app.domain.user.models import User, UserRole


UNCATEGORIZED_SYSTEM_KEY = "uncategorized"


def serialize_project(project: Project, current_user: User) -> dict[str, Any]:
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "visibility": project.visibility.value,
        "status": project.status.value,
        "system_key": project.system_key,
        "created_by": str(project.created_by) if project.created_by else None,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        "archived_at": project.archived_at.isoformat() if project.archived_at else None,
        "can_manage": can_manage_project(project, current_user),
    }


class ProjectService:
    def ensure_uncategorized(self, db: Session) -> Project:
        project = db.scalar(select(Project).where(Project.system_key == UNCATEGORIZED_SYSTEM_KEY))
        if project is None:
            project = Project(
                name="未分类",
                description="未指定项目的发票",
                visibility=ProjectVisibility.system,
                status=ProjectStatus.active,
                system_key=UNCATEGORIZED_SYSTEM_KEY,
            )
            db.add(project)
            db.flush()
        return project

    def list_visible_projects(self, db: Session, current_user: User, *, include_archived: bool = False) -> list[Project]:
        self.ensure_uncategorized(db)
        statement = select(Project)
        if not include_archived:
            statement = statement.where(Project.status == ProjectStatus.active)
        if current_user.role not in {UserRole.finance, UserRole.admin}:
            statement = statement.where(
                or_(
                    Project.visibility == ProjectVisibility.system,
                    Project.visibility == ProjectVisibility.shared,
                    Project.created_by == current_user.id,
                )
            )
        statement = statement.order_by(Project.visibility.asc(), Project.name.asc(), Project.id.asc())
        return list(db.scalars(statement))

    def create_project(self, db: Session, current_user: User, payload: dict[str, Any]) -> Project:
        visibility = ProjectVisibility(payload["visibility"])
        if visibility == ProjectVisibility.system:
            raise AppError("PROJECT_FORBIDDEN", "System projects cannot be created", status_code=403)
        if current_user.role == UserRole.user and visibility != ProjectVisibility.private:
            raise AppError("PROJECT_FORBIDDEN", "You cannot create a shared project", status_code=403)
        name = self._normalize_name(payload["name"])
        self._assert_name_available(db, name, visibility, current_user.id)
        project = Project(
            name=name,
            description=self._normalize_description(payload.get("description")),
            visibility=visibility,
            status=ProjectStatus.active,
            created_by=current_user.id,
        )
        db.add(project)
        db.flush()
        return project

    def get_project(self, db: Session, project_id: UUID) -> Project:
        project = db.get(Project, project_id)
        if project is None:
            raise AppError("PROJECT_NOT_FOUND", "Project was not found", status_code=404)
        return project

    def update_project(self, db: Session, project: Project, current_user: User, payload: dict[str, Any]) -> Project:
        self._assert_manageable(project, current_user)
        if "name" in payload:
            name = self._normalize_name(payload["name"])
            self._assert_name_available(db, name, project.visibility, project.created_by, exclude_id=project.id)
            project.name = name
        if "description" in payload:
            project.description = self._normalize_description(payload["description"])
        db.flush()
        return project

    def archive_project(self, db: Session, project: Project, current_user: User) -> Project:
        self._assert_manageable(project, current_user)
        project.status = ProjectStatus.archived
        project.archived_at = datetime.now(UTC)
        db.flush()
        return project

    def restore_project(self, db: Session, project: Project, current_user: User) -> Project:
        self._assert_manageable(project, current_user)
        project.status = ProjectStatus.active
        project.archived_at = None
        db.flush()
        return project

    def _assert_manageable(self, project: Project, current_user: User) -> None:
        if project.visibility == ProjectVisibility.system:
            raise AppError("PROJECT_SYSTEM_IMMUTABLE", "System projects cannot be changed", status_code=409)
        if can_manage_project(project, current_user):
            return
        raise AppError("PROJECT_FORBIDDEN", "You do not have permission to manage this project", status_code=403)

    def _assert_name_available(
        self,
        db: Session,
        name: str,
        visibility: ProjectVisibility,
        owner_id: UUID | None,
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        statement = select(Project.id).where(func.lower(Project.name) == name.lower())
        if visibility == ProjectVisibility.shared:
            statement = statement.where(Project.visibility == ProjectVisibility.shared)
        else:
            statement = statement.where(
                Project.visibility == ProjectVisibility.private,
                Project.created_by == owner_id,
            )
        if exclude_id is not None:
            statement = statement.where(Project.id != exclude_id)
        if db.scalar(statement) is not None:
            raise AppError("PROJECT_NAME_EXISTS", "A project with this name already exists", status_code=409)

    @staticmethod
    def _normalize_name(value: str) -> str:
        return value.strip()

    @staticmethod
    def _normalize_description(value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


def can_manage_project(project: Project, current_user: User) -> bool:
    if project.visibility == ProjectVisibility.system:
        return False
    if current_user.role == UserRole.admin:
        return True
    if current_user.role == UserRole.finance and project.visibility == ProjectVisibility.shared:
        return True
    return project.visibility == ProjectVisibility.private and str(project.created_by) == str(current_user.id)
