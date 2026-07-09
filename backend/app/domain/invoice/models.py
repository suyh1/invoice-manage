from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class InvoiceStatus(str, enum.Enum):
    uploaded = "uploaded"
    recognizing = "recognizing"
    needs_review = "needs_review"
    confirmed = "confirmed"
    failed = "failed"
    duplicate_suspected = "duplicate_suspected"
    archived = "archived"
    deleted = "deleted"


class DuplicateCheckStatus(str, enum.Enum):
    pending = "pending"
    confirmed_duplicate = "confirmed_duplicate"
    ignored = "ignored"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("invoice_documents.id", ondelete="CASCADE"), nullable=False)
    latest_ocr_job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ocr_jobs.id", name="fk_invoices_latest_ocr_job_id_ocr_jobs", ondelete="SET NULL", use_alter=True)
    )
    invoice_type: Mapped[str | None] = mapped_column(String(120))
    invoice_code: Mapped[str | None] = mapped_column(String(80))
    invoice_number: Mapped[str | None] = mapped_column(String(80))
    invoice_date: Mapped[date | None] = mapped_column(Date)
    seller_name: Mapped[str | None] = mapped_column(String(255))
    seller_tax_id: Mapped[str | None] = mapped_column(String(80))
    buyer_name: Mapped[str | None] = mapped_column(String(255))
    buyer_tax_id: Mapped[str | None] = mapped_column(String(80))
    amount_without_tax: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    amount_with_tax: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    check_code: Mapped[str | None] = mapped_column(String(80))
    currency: Mapped[str] = mapped_column(String(3), default="CNY", nullable=False)
    expense_scene: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status", native_enum=False, create_constraint=True),
        default=InvoiceStatus.uploaded,
        nullable=False,
    )
    is_duplicate_suspected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_ocr_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    normalized_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    extra_fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    confirmed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    document = relationship("InvoiceDocument", back_populates="invoice")
    latest_ocr_job = relationship("OcrJob", foreign_keys=[latest_ocr_job_id], post_update=True)
    ocr_jobs = relationship("OcrJob", foreign_keys="OcrJob.invoice_id", back_populates="invoice")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    corrections = relationship("InvoiceCorrection", back_populates="invoice", cascade="all, delete-orphan")
    duplicate_checks = relationship("DuplicateCheck", foreign_keys="DuplicateCheck.invoice_id", back_populates="invoice")
    confirmed_by_user = relationship("User", foreign_keys=[confirmed_by])

    __table_args__ = (
        Index("ix_invoices_code_number_date", "invoice_code", "invoice_number", "invoice_date"),
        Index("ix_invoices_invoice_number", "invoice_number"),
        Index("ix_invoices_invoice_date", "invoice_date"),
        Index("ix_invoices_seller_name", "seller_name"),
        Index("ix_invoices_buyer_name", "buyer_name"),
        Index("ix_invoices_status_created_at", "status", "created_at"),
        Index("ix_invoices_amount_with_tax", "amount_with_tax"),
    )


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    specification: Mapped[str | None] = mapped_column(String(255))
    unit: Mapped[str | None] = mapped_column(String(80))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    raw_item_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    invoice = relationship("Invoice", back_populates="items")


class InvoiceCorrection(Base):
    __tablename__ = "invoice_corrections"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    field_path: Mapped[str] = mapped_column(String(255), nullable=False)
    ocr_value: Mapped[str | None] = mapped_column(Text)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    invoice = relationship("Invoice", back_populates="corrections")
    changed_by_user = relationship("User")


class DuplicateCheck(Base):
    __tablename__ = "duplicate_checks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    matched_invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    rule: Mapped[str] = mapped_column(String(120), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    status: Mapped[DuplicateCheckStatus] = mapped_column(
        Enum(DuplicateCheckStatus, name="duplicate_check_status", native_enum=False, create_constraint=True),
        default=DuplicateCheckStatus.pending,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    invoice = relationship("Invoice", foreign_keys=[invoice_id], back_populates="duplicate_checks")
    matched_invoice = relationship("Invoice", foreign_keys=[matched_invoice_id])

    __table_args__ = (Index("ix_duplicate_checks_invoice_status", "invoice_id", "status"),)
