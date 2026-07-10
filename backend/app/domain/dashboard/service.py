from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.export.service import ExportService, serialize_export_task
from app.domain.file.models import DocumentStatus, InvoiceDocument
from app.domain.invoice.models import Invoice, InvoiceStatus
from app.domain.ocr.models import OcrJob, OcrJobStatus
from app.domain.review.service import ReviewService
from app.domain.user.models import User, UserRole


ACTIVE_OCR_STATUSES = {
    OcrJobStatus.created,
    OcrJobStatus.queued,
    OcrJobStatus.running,
    OcrJobStatus.retry_scheduled,
    OcrJobStatus.normalizing,
}


class DashboardService:
    def summary(self, db: Session, current_user: User, *, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(UTC)
        review = ReviewService().summary(db, current_user)
        amount_statement = (
            select(func.coalesce(func.sum(Invoice.amount_with_tax), 0))
            .join(Invoice.document)
            .where(
                Invoice.status == InvoiceStatus.confirmed,
                Invoice.confirmed_at >= now - timedelta(days=30),
            )
        )
        queue_statement = (
            select(func.count(OcrJob.id))
            .join(OcrJob.document)
            .where(OcrJob.status.in_(ACTIVE_OCR_STATUSES))
        )
        if current_user.role not in {UserRole.finance, UserRole.admin}:
            amount_statement = amount_statement.where(InvoiceDocument.uploaded_by == current_user.id)
            queue_statement = queue_statement.where(InvoiceDocument.uploaded_by == current_user.id)

        amount = db.scalar(amount_statement) or Decimal("0")
        recent_exports = ExportService().list_tasks(db, current_user)[:5]
        return {
            "needs_review": review["needs_review"],
            "duplicates": review["duplicates"],
            "ocr_failed": review["failed"],
            "confirmed_amount_30d": format(Decimal(str(amount)), "f"),
            "queued_ocr": int(db.scalar(queue_statement) or 0),
            "recent_exports": [serialize_export_task(task) for task in recent_exports],
        }
