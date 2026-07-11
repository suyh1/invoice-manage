from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
import json
from typing import Any
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import assert_invoice_access
from app.core.errors import AppError
from app.domain.file.models import InvoiceDocument
from app.domain.invoice.duplicate import detect_duplicates_for_invoice
from app.domain.invoice.models import Invoice, InvoiceCorrection, InvoiceItem, InvoiceStatus
from app.domain.project.service import ProjectService
from app.domain.user.models import User, UserRole


INVOICE_PATCH_FIELDS = {
    "invoice_type": "string",
    "invoice_code": "string",
    "invoice_number": "string",
    "invoice_date": "date",
    "seller_name": "string",
    "seller_tax_id": "string",
    "buyer_name": "string",
    "buyer_tax_id": "string",
    "amount_without_tax": "decimal",
    "tax_amount": "decimal",
    "amount_with_tax": "decimal",
    "check_code": "string",
    "expense_scene": "string",
}


class InvoiceService:
    def visible_invoice_statement(self, current_user: User) -> Select[tuple[Invoice]]:
        statement = select(Invoice).join(Invoice.document)
        if current_user.role not in {UserRole.finance, UserRole.admin}:
            statement = statement.where(InvoiceDocument.uploaded_by == current_user.id)
        return statement.where(Invoice.status != InvoiceStatus.deleted)

    def list_invoices(self, db: Session, current_user: User, filters: dict[str, Any]) -> dict[str, Any]:
        statement = (
            self.visible_invoice_statement(current_user)
            .options(selectinload(Invoice.document).selectinload(InvoiceDocument.project))
            .order_by(Invoice.created_at.desc(), Invoice.id.desc())
        )
        if current_user.role in {UserRole.finance, UserRole.admin} and filters.get("uploaded_by"):
            statement = statement.where(InvoiceDocument.uploaded_by == UUID(str(filters["uploaded_by"])))

        if filters.get("project_id"):
            statement = statement.where(InvoiceDocument.project_id == UUID(str(filters["project_id"])))

        if filters.get("status"):
            statement = statement.where(Invoice.status == InvoiceStatus(filters["status"]))
        if filters.get("invoice_date_from"):
            statement = statement.where(Invoice.invoice_date >= _parse_date(filters["invoice_date_from"]))
        if filters.get("invoice_date_to"):
            statement = statement.where(Invoice.invoice_date <= _parse_date(filters["invoice_date_to"]))
        if filters.get("uploaded_from"):
            statement = statement.where(InvoiceDocument.created_at >= _parse_datetime(filters["uploaded_from"]))
        if filters.get("uploaded_to"):
            statement = statement.where(InvoiceDocument.created_at <= _parse_datetime(filters["uploaded_to"]))
        if filters.get("amount_min"):
            statement = statement.where(Invoice.amount_with_tax >= Decimal(str(filters["amount_min"])))
        if filters.get("amount_max"):
            statement = statement.where(Invoice.amount_with_tax <= Decimal(str(filters["amount_max"])))
        if filters.get("seller_name"):
            statement = statement.where(Invoice.seller_name.ilike(f"%{filters['seller_name']}%"))
        if filters.get("buyer_name"):
            statement = statement.where(Invoice.buyer_name.ilike(f"%{filters['buyer_name']}%"))
        if filters.get("invoice_number"):
            statement = statement.where(Invoice.invoice_number.ilike(f"%{filters['invoice_number']}%"))
        if filters.get("invoice_code"):
            statement = statement.where(Invoice.invoice_code.ilike(f"%{filters['invoice_code']}%"))
        if filters.get("scene"):
            statement = statement.where(Invoice.expense_scene == filters["scene"])
        if filters.get("file_type"):
            statement = statement.where(InvoiceDocument.file_ext == str(filters["file_type"]).lower())
        if filters.get("duplicate") is not None:
            statement = statement.where(Invoice.is_duplicate_suspected == _parse_bool(filters["duplicate"]))
        if filters.get("q"):
            pattern = f"%{filters['q']}%"
            statement = statement.where(
                or_(
                    Invoice.invoice_number.ilike(pattern),
                    Invoice.invoice_code.ilike(pattern),
                    Invoice.seller_name.ilike(pattern),
                    Invoice.buyer_name.ilike(pattern),
                )
            )

        invoices = list(db.scalars(statement))
        return {"items": [serialize_invoice_summary(invoice) for invoice in invoices], "total": len(invoices)}

    def get_invoice(self, db: Session, invoice_id: UUID, current_user: User) -> Invoice:
        invoice = db.get(
            Invoice,
            invoice_id,
            options=[
                selectinload(Invoice.document).selectinload(InvoiceDocument.project),
                selectinload(Invoice.latest_ocr_job),
                selectinload(Invoice.items),
                selectinload(Invoice.corrections),
            ],
        )
        if invoice is None:
            raise AppError("INVOICE_NOT_FOUND", "Invoice was not found", status_code=404)
        assert_invoice_access(invoice, current_user)
        return invoice

    def update_invoice(self, db: Session, invoice: Invoice, payload: dict[str, Any], current_user: User) -> Invoice:
        assert_invoice_access(invoice, current_user)
        if "project_id" in payload:
            project_id = UUID(str(payload.pop("project_id"))) if payload["project_id"] is not None else None
            project = ProjectService().get_assignable_project(db, project_id, current_user)
            old_project_id = invoice.document.project_id
            if old_project_id != project.id:
                invoice.corrections.append(
                    InvoiceCorrection(
                        field_path="project_id",
                        ocr_value=None,
                        old_value=str(old_project_id) if old_project_id else None,
                        new_value=str(project.id),
                        changed_by=current_user.id,
                    )
                )
                invoice.document.project = project
        for field, field_type in INVOICE_PATCH_FIELDS.items():
            if field not in payload:
                continue
            new_value = _parse_patch_value(payload[field], field_type)
            old_value = getattr(invoice, field)
            if old_value == new_value:
                continue
            correction = InvoiceCorrection(
                invoice=invoice,
                field_path=field,
                ocr_value=_ocr_value(invoice, field),
                old_value=_serialize_scalar(old_value),
                new_value=_serialize_scalar(new_value),
                changed_by=current_user.id,
            )
            setattr(invoice, field, new_value)
            db.add(correction)
        detect_duplicates_for_invoice(db, invoice)
        db.flush()
        return invoice

    def replace_items(self, db: Session, invoice: Invoice, items: list[dict[str, Any]], current_user: User) -> Invoice:
        assert_invoice_access(invoice, current_user)
        old_items = [serialize_invoice_item(item) for item in invoice.items]
        invoice.items.clear()
        for payload in items:
            invoice.items.append(
                InvoiceItem(
                    name=_optional_text(payload.get("name")),
                    specification=_optional_text(payload.get("specification")),
                    unit=_optional_text(payload.get("unit")),
                    quantity=_optional_decimal(payload.get("quantity")),
                    unit_price=_optional_decimal(payload.get("unit_price")),
                    amount=_optional_decimal(payload.get("amount")),
                    tax_rate=_optional_decimal(payload.get("tax_rate")),
                    tax_amount=_optional_decimal(payload.get("tax_amount")),
                )
            )
        new_items = [serialize_invoice_item(item) for item in invoice.items]
        invoice.corrections.append(
            InvoiceCorrection(
                field_path="items",
                ocr_value=json.dumps((invoice.normalized_payload or {}).get("items"), ensure_ascii=False),
                old_value=json.dumps(old_items, ensure_ascii=False),
                new_value=json.dumps(new_items, ensure_ascii=False),
                changed_by=current_user.id,
            )
        )
        db.flush()
        return invoice

    def confirm_invoice(self, db: Session, invoice: Invoice, current_user: User) -> Invoice:
        assert_invoice_access(invoice, current_user)
        invoice.status = InvoiceStatus.confirmed
        invoice.confirmed_by = current_user.id
        invoice.confirmed_at = datetime.now(UTC)
        db.flush()
        return invoice

    def archive_invoice(self, db: Session, invoice: Invoice, current_user: User) -> Invoice:
        assert_invoice_access(invoice, current_user)
        invoice.status = InvoiceStatus.archived
        invoice.archived_at = datetime.now(UTC)
        db.flush()
        return invoice

    def delete_invoice(self, db: Session, invoice: Invoice, current_user: User) -> Invoice:
        assert_invoice_access(invoice, current_user)
        invoice.status = InvoiceStatus.deleted
        db.flush()
        return invoice


def serialize_invoice_summary(invoice: Invoice) -> dict[str, Any]:
    return {
        "id": str(invoice.id),
        "document_id": str(invoice.document_id),
        "invoice_type": invoice.invoice_type,
        "invoice_code": invoice.invoice_code,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "seller_name": invoice.seller_name,
        "buyer_name": invoice.buyer_name,
        "amount_without_tax": _serialize_scalar(invoice.amount_without_tax),
        "tax_amount": _serialize_scalar(invoice.tax_amount),
        "amount_with_tax": _serialize_scalar(invoice.amount_with_tax),
        "currency": invoice.currency,
        "expense_scene": invoice.expense_scene,
        "status": invoice.status.value,
        "is_duplicate_suspected": invoice.is_duplicate_suspected,
        "project": serialize_project_summary(invoice.document.project) if invoice.document and invoice.document.project else None,
        "document": serialize_document(invoice.document) if invoice.document else None,
    }


def serialize_invoice_detail(invoice: Invoice) -> dict[str, Any]:
    detail = serialize_invoice_summary(invoice)
    detail.update(
        {
            "seller_tax_id": invoice.seller_tax_id,
            "buyer_tax_id": invoice.buyer_tax_id,
            "check_code": invoice.check_code,
            "raw_ocr_payload": invoice.raw_ocr_payload,
            "normalized_payload": invoice.normalized_payload,
            "extra_fields": invoice.extra_fields,
            "ocr": serialize_ocr_job(invoice.latest_ocr_job),
            "items": [serialize_invoice_item(item) for item in invoice.items],
            "corrections": [serialize_correction(correction) for correction in invoice.corrections],
            "confirmed_by": str(invoice.confirmed_by) if invoice.confirmed_by else None,
            "confirmed_at": invoice.confirmed_at.isoformat() if invoice.confirmed_at else None,
            "archived_at": invoice.archived_at.isoformat() if invoice.archived_at else None,
        }
    )
    return detail


def serialize_document(document: InvoiceDocument) -> dict[str, Any]:
    return {
        "id": str(document.id),
        "original_filename": document.original_filename,
        "content_type": document.content_type,
        "file_ext": document.file_ext,
        "file_size": document.file_size,
        "sha256": document.sha256,
        "status": document.status.value,
        "created_at": document.created_at.isoformat() if document.created_at else None,
    }


def serialize_project_summary(project) -> dict[str, str]:
    return {
        "id": str(project.id),
        "name": project.name,
        "visibility": project.visibility.value,
        "status": project.status.value,
    }


def serialize_ocr_job(job) -> dict[str, Any] | None:
    if job is None:
        return None
    return {
        "id": str(job.id),
        "provider": job.provider,
        "action": job.action,
        "status": job.status.value,
        "attempt_count": job.attempt_count,
        "request_id": job.request_id,
        "error_code": job.error_code,
        "provider_error_code": job.provider_error_code,
        "duration_ms": (job.raw_request_meta or {}).get("duration_ms"),
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def serialize_invoice_item(item) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "name": item.name,
        "specification": item.specification,
        "unit": item.unit,
        "quantity": _serialize_scalar(item.quantity),
        "unit_price": _serialize_scalar(item.unit_price),
        "amount": _serialize_scalar(item.amount),
        "tax_rate": _serialize_scalar(item.tax_rate),
        "tax_amount": _serialize_scalar(item.tax_amount),
        "raw_item_json": item.raw_item_json,
    }


def serialize_correction(correction: InvoiceCorrection) -> dict[str, Any]:
    return {
        "id": str(correction.id),
        "field_path": correction.field_path,
        "ocr_value": correction.ocr_value,
        "old_value": correction.old_value,
        "new_value": correction.new_value,
        "changed_by": str(correction.changed_by) if correction.changed_by else None,
        "changed_at": correction.changed_at.isoformat() if correction.changed_at else None,
    }


def _parse_patch_value(value: Any, field_type: str) -> Any:
    if value is None:
        return None
    if field_type == "date":
        return _parse_date(value)
    if field_type == "decimal":
        return Decimal(str(value))
    return str(value).strip() or None


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}


def _ocr_value(invoice: Invoice, field: str) -> str | None:
    value = ((invoice.normalized_payload or {}).get("invoice_fields") or {}).get(field)
    return _serialize_scalar(value)


def _serialize_scalar(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip() or None


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    return Decimal(str(value))
