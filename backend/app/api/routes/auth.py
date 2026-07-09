from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.domain.user.models import User, UserStatus
from app.domain.user.service import authenticate_user, create_session_token, user_public_data


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1)


@router.post("/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> dict[str, dict[str, str]]:
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise AppError("AUTH_INVALID_CREDENTIALS", "Invalid email or password", status_code=401)
    if user.status != UserStatus.active:
        raise AppError("AUTH_USER_DISABLED", "User account is disabled", status_code=403)

    settings = get_settings()
    response.set_cookie(
        "session",
        create_session_token(user.id),
        max_age=8 * 60 * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )
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
