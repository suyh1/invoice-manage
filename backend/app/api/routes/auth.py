from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.audit import record_audit_log
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.domain.system.service import bootstrap_first_administrator, is_system_initialized
from app.domain.user.models import User, UserStatus
from app.domain.user.service import authenticate_user, change_password, create_session_token, user_public_data


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1)


class BootstrapRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(min_length=1, max_length=120)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


@router.get("/bootstrap-status")
def bootstrap_status(db: Session = Depends(get_db)) -> dict[str, dict[str, bool]]:
    return {"data": {"initialized": is_system_initialized(db)}}


@router.post("/bootstrap")
def bootstrap(
    payload: BootstrapRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, dict[str, str]]:
    user = bootstrap_first_administrator(
        db,
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
    )
    record_audit_log(
        db,
        actor=user,
        action="auth.bootstrap",
        resource_type="user",
        resource_id=user.id,
        metadata={"email": user.email},
        request=request,
    )
    db.commit()
    db.refresh(user)
    set_session_cookie(response, user)
    return {"data": user_public_data(user)}


@router.post("/login")
def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, dict[str, str]]:
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise AppError("AUTH_INVALID_CREDENTIALS", "Invalid email or password", status_code=401)
    if user.status != UserStatus.active:
        raise AppError("AUTH_USER_DISABLED", "User account is disabled", status_code=403)

    set_session_cookie(response, user)
    record_audit_log(
        db,
        actor=user,
        action="auth.login",
        resource_type="user",
        resource_id=user.id,
        metadata={"email": user.email},
        request=request,
    )
    db.commit()
    return {"data": user_public_data(user)}


@router.post("/logout")
def logout(response: Response) -> dict[str, dict[str, bool]]:
    settings = get_settings()
    response.delete_cookie(
        "session",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )
    return {"data": {"ok": True}}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)) -> dict[str, dict[str, str]]:
    return {"data": user_public_data(current_user)}


@router.patch("/password")
def update_password(
    payload: PasswordChangeRequest,
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, bool]]:
    try:
        change_password(current_user, payload.current_password, payload.new_password)
    except ValueError as exc:
        raise AppError("AUTH_PASSWORD_INCORRECT", "Current password is incorrect", status_code=400) from exc
    record_audit_log(
        db,
        actor=current_user,
        action="auth.password_change",
        resource_type="user",
        resource_id=current_user.id,
        metadata={},
        request=request,
    )
    db.commit()
    db.refresh(current_user)
    set_session_cookie(response, current_user)
    return {"data": {"ok": True}}


def set_session_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        "session",
        create_session_token(user.id, user.session_version),
        max_age=8 * 60 * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )
