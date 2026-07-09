from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.audit import record_audit_log
from app.db.base import Base, import_all_models
from app.domain.user.models import AuditLog, UserRole
from app.domain.user.service import create_user


def make_session():
    import_all_models()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return session_local()


def test_record_audit_log_redacts_sensitive_metadata() -> None:
    with make_session() as session:
        actor = create_user(session, email="admin@example.com", password="password", display_name="Admin", role=UserRole.admin)
        request = SimpleNamespace(
            client=SimpleNamespace(host="203.0.113.7"),
            headers={"user-agent": "pytest-agent/1.0"},
        )

        record_audit_log(
            session,
            actor=actor,
            action="ocr_provider.credential_rotate",
            resource_type="ocr_provider_config",
            resource_id=None,
            metadata={
                "credential": {"secret_id": "AKIDEXAMPLE", "secret_key": "very-sensitive-key"},
                "message": "rotated very-sensitive-key for AKIDEXAMPLE",
            },
            request=request,
            extra_secrets=["AKIDEXAMPLE", "very-sensitive-key"],
        )
        session.commit()

        audit = session.scalar(select(AuditLog))
        assert audit is not None
        assert audit.actor_id == actor.id
        assert audit.action == "ocr_provider.credential_rotate"
        assert audit.resource_type == "ocr_provider_config"
        assert audit.ip_address == "203.0.113.7"
        assert audit.user_agent == "pytest-agent/1.0"
        assert audit.audit_metadata["credential"]["secret_id"] == "***"
        assert audit.audit_metadata["credential"]["secret_key"] == "***"
        assert "AKIDEXAMPLE" not in str(audit.audit_metadata)
        assert "very-sensitive-key" not in str(audit.audit_metadata)
