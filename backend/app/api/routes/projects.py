from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.audit import record_audit_log
from app.db.session import get_db
from app.domain.project.models import ProjectVisibility
from app.domain.project.service import ProjectService, serialize_project
from app.domain.user.models import User


router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


class ProjectCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    visibility: ProjectVisibility


class ProjectPatchPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


@router.get("")
def list_projects(
    include_archived: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = ProjectService()
    projects = service.list_visible_projects(db, current_user, include_archived=include_archived)
    return {"data": [serialize_project(project, current_user) for project in projects]}


@router.post("")
def create_project(
    payload: ProjectCreatePayload,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = ProjectService()
    project = service.create_project(db, current_user, payload.model_dump(mode="json"))
    record_audit_log(
        db,
        actor=current_user,
        action="project.create",
        resource_type="project",
        resource_id=project.id,
        metadata={"name": project.name, "visibility": project.visibility.value},
        request=request,
    )
    db.commit()
    db.refresh(project)
    return {"data": serialize_project(project, current_user)}


@router.patch("/{project_id}")
def update_project(
    project_id: UUID,
    payload: ProjectPatchPayload,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = ProjectService()
    changes = payload.model_dump(exclude_unset=True)
    project = service.update_project(db, service.get_project(db, project_id), current_user, changes)
    record_audit_log(
        db,
        actor=current_user,
        action="project.update",
        resource_type="project",
        resource_id=project.id,
        metadata={"fields": sorted(changes)},
        request=request,
    )
    db.commit()
    db.refresh(project)
    return {"data": serialize_project(project, current_user)}


@router.post("/{project_id}/archive")
def archive_project(
    project_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = ProjectService()
    project = service.archive_project(db, service.get_project(db, project_id), current_user)
    record_audit_log(
        db,
        actor=current_user,
        action="project.archive",
        resource_type="project",
        resource_id=project.id,
        metadata={},
        request=request,
    )
    db.commit()
    db.refresh(project)
    return {"data": serialize_project(project, current_user)}


@router.post("/{project_id}/restore")
def restore_project(
    project_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = ProjectService()
    project = service.restore_project(db, service.get_project(db, project_id), current_user)
    record_audit_log(
        db,
        actor=current_user,
        action="project.restore",
        resource_type="project",
        resource_id=project.id,
        metadata={},
        request=request,
    )
    db.commit()
    db.refresh(project)
    return {"data": serialize_project(project, current_user)}
