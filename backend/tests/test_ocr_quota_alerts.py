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


def test_failed_provider_call_still_consumes_billable_quota() -> None:
    with make_session() as session:
        provider = make_provider()
        session.add(provider)
        session.commit()

        usage = record_provider_call(session, provider, success=False, usage_date=date(2026, 7, 9))

        assert usage.successful_calls == 0
        assert usage.failed_calls == 1
        assert usage.estimated_billable_calls == 1
        assert provider.free_quota_used == 80


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


def test_quota_snapshot_preserves_total_used_semantics_without_false_alert() -> None:
    with make_session() as session:
        provider = make_provider()
        provider.free_quota_total = 1000
        provider.free_quota_used = 4
        session.add(provider)
        session.commit()

        alerts = sync_quota_alerts(session, provider)

        assert alerts == []
        assert provider.free_quota_total - provider.free_quota_used == 996


def test_sync_quota_alerts_refreshes_existing_warning_snapshot() -> None:
    with make_session() as session:
        provider = make_provider()
        provider.free_quota_used = 80
        session.add(provider)
        session.commit()

        first = sync_quota_alerts(session, provider)[0]
        session.commit()
        provider.free_quota_used = 90

        refreshed = sync_quota_alerts(session, provider)[0]

        assert refreshed.id == first.id
        assert refreshed.quota_used == 90
        assert refreshed.quota_remaining == 10
