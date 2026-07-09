from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, import_all_models
from app.domain.ocr.models import OcrProviderConfig, QuotaAlertStatus, QuotaSource
from app.domain.ocr.quota import acknowledge_alert, record_provider_call, sync_quota_alerts
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


def make_provider() -> OcrProviderConfig:
    return OcrProviderConfig(
        provider="tencent",
        display_name="Tencent OCR",
        enabled=True,
        is_default=True,
        quota_source=QuotaSource.manual,
        free_quota_total=100,
        free_quota_used=79,
        quota_warning_percent=80,
        quota_warning_remaining=25,
    )


def test_record_provider_call_updates_daily_usage_and_generates_warning() -> None:
    with make_session() as session:
        provider = make_provider()
        session.add(provider)
        session.commit()

        usage = record_provider_call(session, provider, success=True, usage_date=date(2026, 7, 9))
        alerts = sync_quota_alerts(session, provider)
        session.commit()

        assert usage.successful_calls == 1
        assert usage.failed_calls == 0
        assert provider.free_quota_used == 80
        assert len(alerts) == 1
        assert alerts[0].status == QuotaAlertStatus.active


def test_acknowledge_alert_marks_status() -> None:
    with make_session() as session:
        actor = create_user(
            session,
            email="finance@example.com",
            password="password",
            display_name="Finance",
            role=UserRole.finance,
        )
        provider = make_provider()
        session.add_all([actor, provider])
        session.commit()

        alerts = sync_quota_alerts(session, provider)
        acknowledge_alert(alerts[0], actor)
        session.commit()

        assert alerts[0].status == QuotaAlertStatus.acknowledged
        assert alerts[0].acknowledged_by == actor.id
