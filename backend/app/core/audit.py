from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import redact_secrets
from app.domain.user.models import AuditLog, User


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, dict):
            record.msg = redact_secrets(record.msg)
        if isinstance(record.args, dict):
            record.args = redact_secrets(record.args)
        elif isinstance(record.args, tuple):
            record.args = tuple(redact_secrets(arg) for arg in record.args)
        return True


def install_secret_redaction_filter(logger: logging.Logger | None = None) -> None:
    target = logger or logging.getLogger()
    if not any(isinstance(log_filter, SecretRedactionFilter) for log_filter in target.filters):
        target.addFilter(SecretRedactionFilter())


def record_audit_log(
    db: Session,
    *,
    action: str,
    resource_type: str,
    actor: User | None = None,
    actor_id: UUID | None = None,
    resource_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
    request: Request | Any | None = None,
    extra_secrets: list[str] | tuple[str, ...] | None = None,
) -> AuditLog:
    client = getattr(request, "client", None)
    headers = getattr(request, "headers", None)
    audit = AuditLog(
        actor_id=actor.id if actor is not None else actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        audit_metadata=redact_secrets(metadata or {}, extra_secrets),
        ip_address=getattr(client, "host", None),
        user_agent=headers.get("user-agent") if headers is not None else None,
    )
    db.add(audit)
    db.flush()
    return audit
