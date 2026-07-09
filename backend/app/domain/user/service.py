from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import import_all_models
from app.domain.user.models import User, UserRole, UserStatus


PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 260_000
SESSION_TTL_SECONDS = 8 * 60 * 60

import_all_models()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return "$".join(
        [
            PASSWORD_ALGORITHM,
            str(PASSWORD_ITERATIONS),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, digest_text = password_hash.split("$", 3)
        if algorithm != PASSWORD_ALGORITHM:
            return False
        iterations = int(iterations_text)
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected_digest = base64.urlsafe_b64decode(digest_text.encode("ascii"))
    except (ValueError, TypeError):
        return False

    actual_digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual_digest, expected_digest)


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    display_name: str,
    role: UserRole,
    status: UserStatus = UserStatus.active,
    department: str | None = None,
) -> User:
    user = User(
        email=normalize_email(email),
        password_hash=hash_password(password),
        display_name=display_name,
        role=role,
        status=status,
        department=department,
    )
    db.add(user)
    db.flush()
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def create_session_token(user_id: UUID) -> str:
    expires_at = datetime.now(UTC) + timedelta(seconds=SESSION_TTL_SECONDS)
    payload = {
        "sub": str(user_id),
        "exp": int(expires_at.timestamp()),
    }
    payload_text = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    signature = sign_session_payload(payload_text)
    return f"{payload_text}.{signature}"


def load_user_from_session_token(db: Session, token: str) -> User | None:
    payload = decode_session_token(token)
    if payload is None:
        return None
    try:
        user_id = UUID(str(payload["sub"]))
    except (KeyError, ValueError):
        return None
    return db.get(User, user_id)


def decode_session_token(token: str) -> dict[str, Any] | None:
    try:
        payload_text, signature = token.split(".", 1)
    except ValueError:
        return None
    expected_signature = sign_session_payload(payload_text)
    if not hmac.compare_digest(signature, expected_signature):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_text.encode("ascii")).decode("utf-8"))
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or expires_at <= int(datetime.now(UTC).timestamp()):
        return None
    return payload


def sign_session_payload(payload_text: str) -> str:
    digest = hmac.new(
        get_settings().app_secret_key.encode("utf-8"),
        payload_text.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def user_public_data(user: User) -> dict[str, str]:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role.value,
    }
