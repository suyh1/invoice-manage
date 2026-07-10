from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.core.audit import record_audit_log
from app.db.session import get_db
from app.domain.user.admin_service import AdminUserService, serialize_managed_user
from app.domain.user.models import User, UserRole


router = APIRouter(prefix="/api/v1/admin/users", tags=["admin-users"])


class UserCreatePayload(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(min_length=1, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    role: str = UserRole.user.value
    status: str = "active"


class UserPatchPayload(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    role: str | None = None
    status: str | None = None


class PasswordResetPayload(BaseModel):
    password: str = Field(min_length=12, max_length=256)


@router.get("")
def list_users(
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    del current_user
    return {"data": [serialize_managed_user(user) for user in AdminUserService().list_users(db)]}


@router.post("")
def create_managed_user(
    payload: UserCreatePayload,
    request: Request,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = AdminUserService()
    user = service.create_user(db, payload.model_dump())
    record_audit_log(
        db,
        actor=current_user,
        action="user.create",
        resource_type="user",
        resource_id=user.id,
        metadata={
            "email": user.email,
            "display_name": user.display_name,
            "department": user.department,
            "role": user.role.value,
            "status": user.status.value,
        },
        request=request,
    )
    db.commit()
    db.refresh(user)
    return {"data": serialize_managed_user(user)}


@router.patch("/{user_id}")
def update_managed_user(
    user_id: UUID,
    payload: UserPatchPayload,
    request: Request,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = AdminUserService()
    user = service.get_user(db, user_id)
    changes = payload.model_dump(exclude_unset=True)
    user = service.update_user(db, user, changes)
    record_audit_log(
        db,
        actor=current_user,
        action="user.update",
        resource_type="user",
        resource_id=user.id,
        metadata={"fields": sorted(changes)},
        request=request,
    )
    db.commit()
    db.refresh(user)
    return {"data": serialize_managed_user(user)}


@router.post("/{user_id}/reset-password")
def reset_managed_user_password(
    user_id: UUID,
    payload: PasswordResetPayload,
    request: Request,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = AdminUserService()
    user = service.reset_password(db, service.get_user(db, user_id), payload.password)
    record_audit_log(
        db,
        actor=current_user,
        action="user.password_reset",
        resource_type="user",
        resource_id=user.id,
        metadata={},
        request=request,
    )
    db.commit()
    return {"data": {"ok": True}}
