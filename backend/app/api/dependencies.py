from collections.abc import Callable
from typing import Any

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.domain.user.models import User, UserRole, UserStatus
from app.domain.user.service import load_user_from_session_token


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("session")
    if not token:
        raise AppError("AUTH_REQUIRED", "Authentication is required", status_code=401)

    user = load_user_from_session_token(db, token)
    if user is None:
        raise AppError("AUTH_REQUIRED", "Authentication is required", status_code=401)
    if user.status != UserStatus.active:
        raise AppError("AUTH_USER_DISABLED", "User account is disabled", status_code=403)
    return user


def require_role(*roles: UserRole) -> Callable[[User], User]:
    allowed_roles = set(roles)

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise AppError("AUTH_FORBIDDEN", "You do not have permission to access this resource", status_code=403)
        return current_user

    return dependency


def assert_invoice_access(invoice: Any, current_user: User) -> None:
    if current_user.role in {UserRole.finance, UserRole.admin}:
        return
    uploaded_by = getattr(getattr(invoice, "document", None), "uploaded_by", None)
    if str(uploaded_by) != str(current_user.id):
        raise AppError("AUTH_FORBIDDEN", "You do not have permission to access this invoice", status_code=403)
