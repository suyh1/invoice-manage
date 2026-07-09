from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import CredentialCipher
from app.db.base import Base, import_all_models
from app.domain.ocr.models import OcrProviderConfig
from app.domain.ocr.provider_config import OcrProviderConfigService
from app.domain.user.models import UserRole
from app.domain.user.service import create_user


def make_session() -> Session:
    import_all_models()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return session_local()


def test_provider_config_service_encrypts_credentials_and_redacts_response() -> None:
    with make_session() as session:
        actor = create_user(
            session,
            email="admin@example.com",
            password="password",
            display_name="Admin",
            role=UserRole.admin,
        )
        session.commit()

        service = OcrProviderConfigService()
        provider = service.create_config(
            session,
            {
                "provider": "tencent",
                "display_name": "Tencent OCR",
                "enabled": True,
                "is_default": True,
                "credential": {"secret_id": "AKID123", "secret_key": "SECRET123"},
            },
            actor=actor,
        )
        session.commit()

        assert provider.credential_ciphertext is not None
        assert "AKID123" not in str(provider.credential_ciphertext)
        safe = service.serialize_config(provider)
        assert safe["configured"] is True
        assert safe["credential_fingerprint"].startswith("sha256:")
        assert "credential" not in safe


def test_provider_config_service_switches_default_and_rotates_credentials() -> None:
    with make_session() as session:
        actor = create_user(
            session,
            email="admin@example.com",
            password="password",
            display_name="Admin",
            role=UserRole.admin,
        )
        session.commit()

        service = OcrProviderConfigService()
        first = service.create_config(
            session,
            {
                "provider": "tencent",
                "display_name": "Tencent OCR",
                "enabled": True,
                "is_default": True,
                "credential": {"secret_id": "AKID1", "secret_key": "SECRET1"},
            },
            actor=actor,
        )
        second = service.create_config(
            session,
            {
                "provider": "mock",
                "display_name": "Mock OCR",
                "enabled": True,
                "is_default": False,
            },
            actor=actor,
        )
        old_fingerprint = first.credential_fingerprint
        service.set_default(session, second, actor=actor)
        service.rotate_credentials(
            session,
            first,
            credential={"secret_id": "AKID2", "secret_key": "SECRET2"},
            actor=actor,
        )
        session.commit()

        assert session.get(OcrProviderConfig, first.id).is_default is False
        assert session.get(OcrProviderConfig, second.id).is_default is True
        assert session.get(OcrProviderConfig, first.id).credential_fingerprint != old_fingerprint


def test_provider_config_service_creates_new_default_when_existing_default_is_present() -> None:
    with make_session() as session:
        actor = create_user(
            session,
            email="admin@example.com",
            password="password",
            display_name="Admin",
            role=UserRole.admin,
        )
        session.commit()

        service = OcrProviderConfigService()
        first = service.create_config(
            session,
            {
                "provider": "tencent",
                "display_name": "Tencent OCR",
                "enabled": True,
                "is_default": True,
            },
            actor=actor,
        )
        second = service.create_config(
            session,
            {
                "provider": "mock",
                "display_name": "Mock OCR",
                "enabled": True,
                "is_default": True,
            },
            actor=actor,
        )
        session.commit()

        assert session.get(OcrProviderConfig, first.id).is_default is False
        assert session.get(OcrProviderConfig, second.id).is_default is True
