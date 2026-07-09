from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentStatus(str, enum.Enum):
    uploaded = "uploaded"
    ocr_queued = "ocr_queued"
    ocr_running = "ocr_running"
    ocr_done = "ocr_done"
    ocr_failed = "ocr_failed"
    deleted = "deleted"


class InvoiceDocument(Base):
    __tablename__ = "invoice_documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID | None]
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_ext: Mapped[str] = mapped_column(String(16), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    base64_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    page_count: Mapped[int | None]
    image_width: Mapped[int | None]
    image_height: Mapped[int | None]
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", native_enum=False, create_constraint=True),
        default=DocumentStatus.uploaded,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    uploaded_by_user = relationship("User", back_populates="uploaded_documents")
    ocr_jobs = relationship("OcrJob", back_populates="document")
    invoice = relationship("Invoice", back_populates="document", uselist=False)

    __table_args__ = (
        Index("ix_invoice_documents_uploaded_by_created_at", "uploaded_by", "created_at"),
        Index("ix_invoice_documents_sha256", "sha256"),
        Index("ix_invoice_documents_status_created_at", "status", "created_at"),
    )
