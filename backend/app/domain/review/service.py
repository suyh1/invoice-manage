from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.domain.file.models import DocumentStatus, InvoiceDocument
from app.domain.invoice.models import Invoice, InvoiceStatus
from app.domain.invoice.service import serialize_invoice_summary, serialize_ocr_job, serialize_project_summary
from app.domain.user.models import User, UserRole


class ReviewService:
    def summary(self, db: Session, current_user: User) -> dict[str, int]:
        return {
            "needs_review": self._invoice_count(db, current_user, Invoice.status == InvoiceStatus.needs_review),
            "duplicates": self._invoice_count(
                db,
                current_user,
                or_(Invoice.status == InvoiceStatus.duplicate_suspected, Invoice.is_duplicate_suspected.is_(True)),
            ),
            "failed": self._failed_document_count(db, current_user),
        }

    def list_items(self, db: Session, current_user: User, queue: str) -> dict[str, Any]:
        if queue == "failed":
            documents = self._failed_documents(db, current_user)
            return {"items": [self._serialize_failed_document(document) for document in documents], "total": len(documents)}

        condition = (
            Invoice.status == InvoiceStatus.needs_review
            if queue == "needs_review"
            else or_(Invoice.status == InvoiceStatus.duplicate_suspected, Invoice.is_duplicate_suspected.is_(True))
        )
        statement = (
            select(Invoice)
            .join(Invoice.document)
            .options(
                selectinload(Invoice.document).selectinload(InvoiceDocument.project),
                selectinload(Invoice.latest_ocr_job),
            )
            .where(condition)
            .order_by(Invoice.created_at.asc(), Invoice.id.asc())
        )
        statement = self._scope_invoice_statement(statement, current_user)
        invoices = list(db.scalars(statement))
        return {"items": [self._serialize_invoice(invoice) for invoice in invoices], "total": len(invoices)}

    def _invoice_count(self, db: Session, current_user: User, condition) -> int:
        statement = select(func.count(Invoice.id)).join(Invoice.document).where(condition)
        statement = self._scope_invoice_statement(statement, current_user)
        return int(db.scalar(statement) or 0)

    def _failed_document_count(self, db: Session, current_user: User) -> int:
        statement = select(func.count(InvoiceDocument.id)).where(InvoiceDocument.status == DocumentStatus.ocr_failed)
        if current_user.role not in {UserRole.finance, UserRole.admin}:
            statement = statement.where(InvoiceDocument.uploaded_by == current_user.id)
        return int(db.scalar(statement) or 0)

    def _failed_documents(self, db: Session, current_user: User) -> list[InvoiceDocument]:
        statement = (
            select(InvoiceDocument)
            .options(selectinload(InvoiceDocument.project), selectinload(InvoiceDocument.ocr_jobs))
            .where(InvoiceDocument.status == DocumentStatus.ocr_failed)
            .order_by(InvoiceDocument.created_at.asc(), InvoiceDocument.id.asc())
        )
        if current_user.role not in {UserRole.finance, UserRole.admin}:
            statement = statement.where(InvoiceDocument.uploaded_by == current_user.id)
        return list(db.scalars(statement))

    @staticmethod
    def _scope_invoice_statement(statement, current_user: User):
        if current_user.role not in {UserRole.finance, UserRole.admin}:
            statement = statement.where(InvoiceDocument.uploaded_by == current_user.id)
        return statement

    @staticmethod
    def _serialize_invoice(invoice: Invoice) -> dict[str, Any]:
        item = serialize_invoice_summary(invoice)
        item.update(
            {
                "kind": "invoice",
                "invoice_id": str(invoice.id),
                "ocr": serialize_ocr_job(invoice.latest_ocr_job),
            }
        )
        return item

    @staticmethod
    def _serialize_failed_document(document: InvoiceDocument) -> dict[str, Any]:
        latest_job = max(document.ocr_jobs, key=lambda job: (str(job.created_at or ""), str(job.id)), default=None)
        return {
            "kind": "document",
            "invoice_id": None,
            "document_id": str(document.id),
            "status": document.status.value,
            "project": serialize_project_summary(document.project) if document.project else None,
            "document": {
                "id": str(document.id),
                "original_filename": document.original_filename,
                "file_ext": document.file_ext,
                "status": document.status.value,
                "created_at": document.created_at.isoformat() if document.created_at else None,
            },
            "ocr": serialize_ocr_job(latest_job),
        }
