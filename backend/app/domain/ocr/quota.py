from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.ocr.models import (
    OcrProviderConfig,
    OcrProviderUsageDaily,
    OcrQuotaAlert,
    QuotaAlertLevel,
    QuotaAlertStatus,
)


def quota_snapshot(provider_config: OcrProviderConfig) -> dict[str, int | str | None]:
    total = provider_config.free_quota_total
    used = provider_config.free_quota_used
    remaining = max((total or 0) - (used or 0), 0) if total is not None and used is not None else None
    used_percent = int((used or 0) * 100 / total) if total not in (None, 0) and used is not None else None
    level = determine_alert_level(provider_config)
    return {
        "source": provider_config.quota_source.value,
        "free_quota_total": total,
        "free_quota_used": used,
        "free_quota_remaining": remaining,
        "used_percent": used_percent,
        "warning_percent": provider_config.quota_warning_percent,
        "warning_remaining": provider_config.quota_warning_remaining,
        "reset_at": provider_config.quota_reset_at.isoformat() if provider_config.quota_reset_at else None,
        "alert_level": level.value if level else "none",
    }


def determine_alert_level(provider_config: OcrProviderConfig) -> QuotaAlertLevel | None:
    total = provider_config.free_quota_total
    used = provider_config.free_quota_used
    if total is None or used is None:
        return None

    remaining = max(total - used, 0)
    used_percent = 100 if total == 0 else int(used * 100 / total)
    if remaining <= 0 or used_percent >= 100:
        return QuotaAlertLevel.critical
    if remaining <= provider_config.quota_warning_remaining or used_percent >= provider_config.quota_warning_percent:
        return QuotaAlertLevel.warning
    return None


def record_provider_call(
    db: Session,
    provider_config: OcrProviderConfig,
    *,
    success: bool,
    usage_date: date | None = None,
) -> OcrProviderUsageDaily:
    usage_date = usage_date or datetime.now(UTC).date()
    usage = db.scalar(
        select(OcrProviderUsageDaily).where(
            OcrProviderUsageDaily.provider_config_id == provider_config.id,
            OcrProviderUsageDaily.usage_date == usage_date,
            OcrProviderUsageDaily.action == provider_config.action,
        )
    )
    if usage is None:
        usage = OcrProviderUsageDaily(
            provider_config_id=provider_config.id,
            usage_date=usage_date,
            provider=provider_config.provider,
            action=provider_config.action,
            successful_calls=0,
            failed_calls=0,
            estimated_billable_calls=0,
        )
        db.add(usage)

    if success:
        usage.successful_calls += 1
    else:
        usage.failed_calls += 1
    usage.estimated_billable_calls += 1
    if provider_config.free_quota_used is not None:
        provider_config.free_quota_used += 1
    db.flush()
    return usage


def sync_quota_alerts(db: Session, provider_config: OcrProviderConfig) -> list[OcrQuotaAlert]:
    level = determine_alert_level(provider_config)
    active_alerts = list(
        db.scalars(
            select(OcrQuotaAlert).where(
                OcrQuotaAlert.provider_config_id == provider_config.id,
                OcrQuotaAlert.status == QuotaAlertStatus.active,
            )
        )
    )

    if level is None:
        for alert in active_alerts:
            alert.status = QuotaAlertStatus.resolved
            alert.resolved_at = datetime.now(UTC)
        db.flush()
        return []

    for alert in active_alerts:
        if alert.level != level:
            alert.status = QuotaAlertStatus.resolved
            alert.resolved_at = datetime.now(UTC)

    existing = next((alert for alert in active_alerts if alert.level == level and alert.status == QuotaAlertStatus.active), None)
    remaining = None
    if provider_config.free_quota_total is not None and provider_config.free_quota_used is not None:
        remaining = max(provider_config.free_quota_total - provider_config.free_quota_used, 0)
    if existing is None:
        existing = OcrQuotaAlert(
            provider_config_id=provider_config.id,
            level=level,
            status=QuotaAlertStatus.active,
            message=build_alert_message(level, provider_config),
            quota_total=provider_config.free_quota_total,
            quota_used=provider_config.free_quota_used,
            quota_remaining=remaining,
        )
        db.add(existing)
    else:
        existing.message = build_alert_message(level, provider_config)
        existing.quota_total = provider_config.free_quota_total
        existing.quota_used = provider_config.free_quota_used
        existing.quota_remaining = remaining
    db.flush()
    return [existing]


def build_alert_message(level: QuotaAlertLevel, provider_config: OcrProviderConfig) -> str:
    if level == QuotaAlertLevel.critical:
        return f"{provider_config.display_name} OCR quota has been exhausted or is in a critical state"
    return f"{provider_config.display_name} OCR quota is nearing the configured threshold"


def acknowledge_alert(alert: OcrQuotaAlert, actor) -> OcrQuotaAlert:
    alert.status = QuotaAlertStatus.acknowledged
    alert.acknowledged_by = actor.id
    alert.acknowledged_at = datetime.now(UTC)
    return alert
