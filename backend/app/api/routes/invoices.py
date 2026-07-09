from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.errors import AppError
from app.db.session import get_db
from app.domain.invoice.duplicate import serialize_duplicate_check
from app.domain.invoice.models import DuplicateCheck, DuplicateCheckStatus
from app.domain.invoice.service import InvoiceService, serialize_invoice_detail
from app.domain.user.models import User, UserRole


router = APIRouter(prefix="/api/v1/invoices", tags=["invoices"])
duplicate_router = APIRouter(prefix="/api/v1/duplicate-checks", tags=["duplicate-checks"])


class InvoicePatchPayload(BaseModel):
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
        "q": q,
    }
    return {"data": InvoiceService().list_invoices(db, current_user, filters)}


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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = InvoiceService()
    invoice = service.get_invoice(db, invoice_id, current_user)
    updated = service.update_invoice(db, invoice, payload.model_dump(exclude_unset=True), current_user)
    db.commit()
    db.refresh(updated)
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
