from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import TENCENT_OCR_DEFAULTS
from app.db.base import Base, JSON_VARIANT, TimestampMixin


class OcrJobStatus(str, enum.Enum):
    created = "created"
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed_retryable = "failed_retryable"
    retry_scheduled = "retry_scheduled"
    failed_final = "failed_final"
    normalizing = "normalizing"
    completed = "completed"
    canceled = "canceled"


class QuotaSource(str, enum.Enum):
    manual = "manual"
    provider_api = "provider_api"
    estimated = "estimated"


class QuotaAlertLevel(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class QuotaAlertStatus(str, enum.Enum):
    active = "active"
    acknowledged = "acknowledged"
    resolved = "resolved"


class OcrProviderConfig(Base, TimestampMixin):
    __tablename__ = "ocr_provider_configs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    credential_ciphertext: Mapped[dict[str, Any] | None] = mapped_column(JSON_VARIANT)
    credential_fingerprint: Mapped[str | None] = mapped_column(String(120))
    endpoint: Mapped[str] = mapped_column(String(255), default=TENCENT_OCR_DEFAULTS.endpoint, nullable=False)
    region: Mapped[str] = mapped_column(String(80), default=TENCENT_OCR_DEFAULTS.region, nullable=False)
    action: Mapped[str] = mapped_column(String(80), default=TENCENT_OCR_DEFAULTS.action, nullable=False)
    api_version: Mapped[str] = mapped_column(String(40), default=TENCENT_OCR_DEFAULTS.api_version, nullable=False)
    qps_limit: Mapped[int] = mapped_column(default=TENCENT_OCR_DEFAULTS.qps_limit, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(default=30, nullable=False)
    quota_source: Mapped[QuotaSource] = mapped_column(
        Enum(QuotaSource, name="quota_source", native_enum=False, create_constraint=True),
        default=QuotaSource.manual,
        nullable=False,
    )
    free_quota_total: Mapped[int | None]
    free_quota_used: Mapped[int | None]
    quota_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quota_warning_percent: Mapped[int] = mapped_column(default=TENCENT_OCR_DEFAULTS.quota_warning_percent, nullable=False)
    quota_warning_remaining: Mapped[int] = mapped_column(default=TENCENT_OCR_DEFAULTS.quota_warning_remaining, nullable=False)
    last_test_status: Mapped[str | None] = mapped_column(String(40))
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    created_by_user = relationship("User", foreign_keys=[created_by], back_populates="configured_ocr_providers")
    updated_by_user = relationship("User", foreign_keys=[updated_by])
    ocr_jobs = relationship("OcrJob", back_populates="provider_config")
    usage_days = relationship("OcrProviderUsageDaily", back_populates="provider_config")
    quota_alerts = relationship("OcrQuotaAlert", back_populates="provider_config")

    __table_args__ = (
        Index(
            "ix_ocr_provider_configs_single_default",
            "is_default",
            unique=True,
            postgresql_where=text("enabled AND is_default"),
            sqlite_where=text("enabled = 1 AND is_default = 1"),
        ),
        Index("ix_ocr_provider_configs_provider_enabled", "provider", "enabled"),
    )


class OcrProviderUsageDaily(Base, TimestampMixin):
    __tablename__ = "ocr_provider_usage_daily"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider_config_id: Mapped[UUID] = mapped_column(ForeignKey("ocr_provider_configs.id", ondelete="CASCADE"), nullable=False)
    usage_date: Mapped[date] = mapped_column(nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    successful_calls: Mapped[int] = mapped_column(default=0, nullable=False)
    failed_calls: Mapped[int] = mapped_column(default=0, nullable=False)
    estimated_billable_calls: Mapped[int] = mapped_column(default=0, nullable=False)
    provider_reported_used: Mapped[int | None]

    provider_config = relationship("OcrProviderConfig", back_populates="usage_days")

    __table_args__ = (UniqueConstraint("provider_config_id", "usage_date", "action", name="uq_ocr_provider_usage_daily_provider_date_action"),)


class OcrQuotaAlert(Base):
    __tablename__ = "ocr_quota_alerts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider_config_id: Mapped[UUID] = mapped_column(ForeignKey("ocr_provider_configs.id", ondelete="CASCADE"), nullable=False)
    level: Mapped[QuotaAlertLevel] = mapped_column(
        Enum(QuotaAlertLevel, name="quota_alert_level", native_enum=False, create_constraint=True), nullable=False
    )
    status: Mapped[QuotaAlertStatus] = mapped_column(
        Enum(QuotaAlertStatus, name="quota_alert_status", native_enum=False, create_constraint=True),
        default=QuotaAlertStatus.active,
        nullable=False,
    )
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    quota_total: Mapped[int | None]
    quota_used: Mapped[int | None]
    quota_remaining: Mapped[int | None]
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    acknowledged_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    provider_config = relationship("OcrProviderConfig", back_populates="quota_alerts")
    acknowledged_by_user = relationship("User")

    __table_args__ = (Index("ix_ocr_quota_alerts_status_level", "status", "level"),)


class OcrJob(Base):
    __tablename__ = "ocr_jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("invoice_documents.id", ondelete="CASCADE"), nullable=False)
    invoice_id: Mapped[UUID | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"))
    provider_config_id: Mapped[UUID] = mapped_column(ForeignKey("ocr_provider_configs.id", ondelete="RESTRICT"), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    region: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[OcrJobStatus] = mapped_column(
        Enum(OcrJobStatus, name="ocr_job_status", native_enum=False, create_constraint=True),
        default=OcrJobStatus.created,
        nullable=False,
    )
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(120))
    error_code: Mapped[str | None] = mapped_column(String(120))
    provider_error_code: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    raw_request_meta: Mapped[dict[str, Any] | None] = mapped_column(JSON_VARIANT)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSON_VARIANT)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    document = relationship("InvoiceDocument", back_populates="ocr_jobs")
    provider_config = relationship("OcrProviderConfig", back_populates="ocr_jobs")
    invoice = relationship("Invoice", foreign_keys=[invoice_id], back_populates="ocr_jobs")

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ocr_jobs_idempotency_key"),
        Index("ix_ocr_jobs_document_id_created_at", "document_id", "created_at"),
        Index("ix_ocr_jobs_status_created_at", "status", "created_at"),
    )
