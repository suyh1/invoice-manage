from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.audit import record_audit_log
from app.core.errors import AppError
from app.db.session import get_db
from app.domain.invoice.duplicate import serialize_duplicate_check
from app.domain.invoice.models import DuplicateCheck, DuplicateCheckStatus, InvoiceStatus
from app.domain.invoice.service import InvoiceService, serialize_invoice_detail
from app.domain.user.models import User, UserRole


router = APIRouter(prefix="/api/v1/invoices", tags=["invoices"])
duplicate_router = APIRouter(prefix="/api/v1/duplicate-checks", tags=["duplicate-checks"])


class InvoicePatchPayload(BaseModel):
    project_id: UUID | None = None
    invoice_type: str | None = None
    invoice_code: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    seller_name: str | None = None
    seller_tax_id: str | None = None
    buyer_name: str | None = None
    buyer_tax_id: str | None = None
    amount_without_tax: str | None = None
    tax_amount: str | None = None
    amount_with_tax: str | None = None
    check_code: str | None = None
    expense_scene: str | None = None


class InvoiceItemPayload(BaseModel):
    id: UUID | None = None
    name: str | None = None
    specification: str | None = None
    unit: str | None = None
    quantity: str | None = None
    unit_price: str | None = None
    amount: str | None = None
    tax_rate: str | None = None
    tax_amount: str | None = None


class InvoiceItemsPayload(BaseModel):
    items: list[InvoiceItemPayload] = Field(max_length=500)


class BulkConfirmPayload(BaseModel):
    invoice_ids: list[UUID] = Field(min_length=1, max_length=100)


@router.get("")
def list_invoices(
    status: str | None = None,
    invoice_date_from: str | None = None,
    invoice_date_to: str | None = None,
    uploaded_from: str | None = None,
    uploaded_to: str | None = None,
    amount_min: str | None = None,
    amount_max: str | None = None,
    seller_name: str | None = None,
    buyer_name: str | None = None,
    invoice_number: str | None = None,
    invoice_code: str | None = None,
    scene: str | None = None,
    file_type: str | None = None,
    duplicate: str | None = None,
    project_id: UUID | None = None,
    uploaded_by: UUID | None = None,
    q: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    filters = {
        "status": status,
        "invoice_date_from": invoice_date_from,
        "invoice_date_to": invoice_date_to,
        "uploaded_from": uploaded_from,
        "uploaded_to": uploaded_to,
        "amount_min": amount_min,
        "amount_max": amount_max,
        "seller_name": seller_name,
        "buyer_name": buyer_name,
        "invoice_number": invoice_number,
        "invoice_code": invoice_code,
        "scene": scene,
        "file_type": file_type,
        "duplicate": duplicate,
        "project_id": project_id,
        "uploaded_by": uploaded_by,
        "q": q,
    }
    return {"data": InvoiceService().list_invoices(db, current_user, filters)}


@router.post("/bulk-confirm")
def bulk_confirm_invoices(
    payload: BulkConfirmPayload,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = InvoiceService()
    invoices = [service.get_invoice(db, invoice_id, current_user) for invoice_id in payload.invoice_ids]
    if any(
        invoice.status != InvoiceStatus.needs_review or invoice.is_duplicate_suspected
        for invoice in invoices
    ):
        raise AppError(
            "REVIEW_BULK_CONFIRM_BLOCKED",
            "Only clean invoices awaiting review can be confirmed in bulk",
            status_code=409,
        )

    for invoice in invoices:
        service.confirm_invoice(db, invoice, current_user)
        record_audit_log(
            db,
            actor=current_user,
            action="invoice.confirm",
            resource_type="invoice",
            resource_id=invoice.id,
            metadata={"source": "bulk"},
            request=request,
        )
    record_audit_log(
        db,
        actor=current_user,
        action="invoice.bulk_confirm",
        resource_type="invoice_batch",
        resource_id=None,
        metadata={"invoice_ids": [str(invoice.id) for invoice in invoices]},
        request=request,
    )
    db.commit()
    return {"data": {"confirmed_ids": [str(invoice.id) for invoice in invoices]}}


@router.get("/{invoice_id}")
def get_invoice(
    invoice_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    invoice = InvoiceService().get_invoice(db, invoice_id, current_user)
    return {"data": serialize_invoice_detail(invoice)}


@router.patch("/{invoice_id}")
def update_invoice(
    invoice_id: UUID,
    payload: InvoicePatchPayload,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = InvoiceService()
    invoice = service.get_invoice(db, invoice_id, current_user)
    changes = payload.model_dump(exclude_unset=True)
    updated = service.update_invoice(db, invoice, changes, current_user)
    if changes:
        record_audit_log(
            db,
            actor=current_user,
            action="invoice.correct",
            resource_type="invoice",
            resource_id=updated.id,
            metadata={"fields": list(changes.keys())},
            request=request,
        )
    db.commit()
    db.refresh(updated)
    return {"data": serialize_invoice_detail(updated)}


@router.put("/{invoice_id}/items")
def replace_invoice_items(
    invoice_id: UUID,
    payload: InvoiceItemsPayload,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = InvoiceService()
    invoice = service.get_invoice(db, invoice_id, current_user)
    updated = service.replace_items(
        db,
        invoice,
        [item.model_dump(exclude={"id"}) for item in payload.items],
        current_user,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="invoice.items_update",
        resource_type="invoice",
        resource_id=updated.id,
        metadata={"item_count": len(payload.items)},
        request=request,
    )
    db.commit()
    return {"data": serialize_invoice_detail(updated)}


@router.post("/{invoice_id}/confirm")
def confirm_invoice(
    invoice_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = InvoiceService()
    invoice = service.get_invoice(db, invoice_id, current_user)
    confirmed = service.confirm_invoice(db, invoice, current_user)
    db.commit()
    db.refresh(confirmed)
    return {"data": serialize_invoice_detail(confirmed)}


@router.post("/{invoice_id}/archive")
def archive_invoice(
    invoice_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = InvoiceService()
    invoice = service.get_invoice(db, invoice_id, current_user)
    archived = service.archive_invoice(db, invoice, current_user)
    db.commit()
    db.refresh(archived)
    return {"data": serialize_invoice_detail(archived)}


@router.delete("/{invoice_id}")
def delete_invoice(
    invoice_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = InvoiceService()
    invoice = service.get_invoice(db, invoice_id, current_user)
    deleted = service.delete_invoice(db, invoice, current_user)
    db.commit()
    db.refresh(deleted)
    return {"data": serialize_invoice_detail(deleted)}


@router.get("/{invoice_id}/duplicate-checks")
def list_duplicate_checks(
    invoice_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    invoice = InvoiceService().get_invoice(db, invoice_id, current_user)
    checks = sorted(invoice.duplicate_checks, key=lambda check: check.score or 0, reverse=True)
    return {"data": [serialize_duplicate_check(check) for check in checks]}


@duplicate_router.post("/{check_id}/confirm")
def confirm_duplicate_check(
    check_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    check = _get_duplicate_check_for_finance(db, check_id, current_user)
    check.status = DuplicateCheckStatus.confirmed_duplicate
    db.commit()
    db.refresh(check)
    return {"data": serialize_duplicate_check(check)}


@duplicate_router.post("/{check_id}/ignore")
def ignore_duplicate_check(
    check_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    check = _get_duplicate_check_for_finance(db, check_id, current_user)
    check.status = DuplicateCheckStatus.ignored
    db.commit()
    db.refresh(check)
    return {"data": serialize_duplicate_check(check)}


def _get_duplicate_check_for_finance(db: Session, check_id: UUID, current_user: User) -> DuplicateCheck:
    if current_user.role not in {UserRole.finance, UserRole.admin}:
        raise AppError("AUTH_FORBIDDEN", "You do not have permission to manage duplicate checks", status_code=403)
    check = db.get(DuplicateCheck, check_id)
    if check is None:
        raise AppError("DUPLICATE_CHECK_NOT_FOUND", "Duplicate check was not found", status_code=404)
    return check
