from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domain.user.models import User, UserRole, UserStatus
from app.domain.user.service import create_user, get_user_by_email, hash_password


def serialize_managed_user(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "department": user.department,
        "role": user.role.value,
        "status": user.status.value,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


class AdminUserService:
    def list_users(self, db: Session) -> list[User]:
        return list(db.scalars(select(User).order_by(User.created_at.asc(), User.id.asc())))

    def create_user(self, db: Session, payload: dict[str, Any]) -> User:
        if get_user_by_email(db, payload["email"]) is not None:
            raise AppError("USER_EMAIL_EXISTS", "A user with this email already exists", status_code=409)
        return create_user(
            db,
            email=payload["email"],
            password=payload["password"],
            display_name=payload["display_name"],
            role=UserRole(payload.get("role", UserRole.user.value)),
            status=UserStatus(payload.get("status", UserStatus.active.value)),
            department=payload.get("department"),
        )

    def get_user(self, db: Session, user_id: UUID) -> User:
        user = db.get(User, user_id)
        if user is None:
            raise AppError("USER_NOT_FOUND", "User was not found", status_code=404)
        return user

    def update_user(self, db: Session, user: User, payload: dict[str, Any]) -> User:
        next_role = UserRole(payload["role"]) if "role" in payload else user.role
        next_status = UserStatus(payload["status"]) if "status" in payload else user.status
        if (
            user.role == UserRole.admin
            and user.status == UserStatus.active
            and (next_role != UserRole.admin or next_status != UserStatus.active)
            and self._active_admin_count(db) <= 1
        ):
            raise AppError(
                "AUTH_LAST_ADMIN_REQUIRED",
                "At least one active administrator is required",
                status_code=409,
            )

        for field in ("display_name", "department"):
            if field in payload:
                setattr(user, field, payload[field])
        user.role = next_role
        user.status = next_status
        db.flush()
        return user

    def reset_password(self, db: Session, user: User, password: str) -> User:
        user.password_hash = hash_password(password)
        user.session_version = (user.session_version or 1) + 1
        db.flush()
        return user

    def _active_admin_count(self, db: Session) -> int:
        return int(
            db.scalar(
                select(func.count(User.id)).where(
                    User.role == UserRole.admin,
                    User.status == UserStatus.active,
                )
            )
            or 0
        )
