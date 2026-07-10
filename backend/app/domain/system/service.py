from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domain.system.models import SystemState
from app.domain.user.models import User, UserRole
from app.domain.user.service import create_user


SYSTEM_STATE_ID = 1


def is_system_initialized(db: Session) -> bool:
    state = db.get(SystemState, SYSTEM_STATE_ID)
    if state is not None and state.initialized_at is not None:
        return True
    return bool(db.scalar(select(func.count(User.id))) or 0)


def bootstrap_first_administrator(
    db: Session,
    *,
    email: str,
    password: str,
    display_name: str,
) -> User:
    state = db.scalar(
        select(SystemState).where(SystemState.id == SYSTEM_STATE_ID).with_for_update()
    )
    if state is None:
        state = SystemState(id=SYSTEM_STATE_ID)
        db.add(state)
        db.flush()

    if state.initialized_at is not None or (db.scalar(select(func.count(User.id))) or 0) > 0:
        raise AppError(
            "AUTH_BOOTSTRAP_COMPLETE",
            "System initialization is already complete",
            status_code=409,
        )

    user = create_user(
        db,
        email=email,
        password=password,
        display_name=display_name,
        role=UserRole.admin,
    )
    state.initialized_at = datetime.now(UTC)
    state.initialized_by = user.id
    db.flush()
    return user
