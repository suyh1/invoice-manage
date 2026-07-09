from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.invoice.models import DuplicateCheck, Invoice, InvoiceStatus


STRONG_RULE = "code_number_date_amount"
WEAK_RULE = "number_date_seller_amount"
ELECTRONIC_RULE = "electronic_number_date_amount"


def detect_duplicates_for_invoice(db: Session, invoice: Invoice) -> list[DuplicateCheck]:
    db.flush()
    created_checks: list[DuplicateCheck] = []
    candidates = list(
        db.scalars(
            select(Invoice).where(
                Invoice.id != invoice.id,
                Invoice.status != InvoiceStatus.deleted,
            )
        )
    )
    for candidate in candidates:
        match = _match_rule(invoice, candidate)
        if match is None:
            continue
        rule, score = match
        existing = db.scalar(
            select(DuplicateCheck).where(
                DuplicateCheck.invoice_id == invoice.id,
                DuplicateCheck.matched_invoice_id == candidate.id,
                DuplicateCheck.rule == rule,
            )
        )
        if existing is not None:
            continue
        check = DuplicateCheck(invoice=invoice, matched_invoice=candidate, rule=rule, score=score)
        db.add(check)
        created_checks.append(check)

    if created_checks:
        invoice.is_duplicate_suspected = True
        if invoice.status not in {InvoiceStatus.confirmed, InvoiceStatus.archived, InvoiceStatus.deleted}:
            invoice.status = InvoiceStatus.duplicate_suspected
        for check in created_checks:
            check.matched_invoice.is_duplicate_suspected = True
    db.flush()
    return created_checks


def serialize_duplicate_check(check: DuplicateCheck) -> dict[str, object]:
    return {
        "id": str(check.id),
        "invoice_id": str(check.invoice_id),
        "matched_invoice_id": str(check.matched_invoice_id),
        "rule": check.rule,
        "score": format(check.score, "f"),
        "status": check.status.value,
        "created_at": check.created_at.isoformat() if check.created_at else None,
    }


def _match_rule(invoice: Invoice, candidate: Invoice) -> tuple[str, Decimal] | None:
    if (
        invoice.invoice_code
        and candidate.invoice_code
        and _same(invoice.invoice_code, candidate.invoice_code)
        and _same(invoice.invoice_number, candidate.invoice_number)
        and invoice.invoice_date == candidate.invoice_date
        and invoice.amount_with_tax == candidate.amount_with_tax
    ):
        return STRONG_RULE, Decimal("1.0000")
    if (
        _same(invoice.invoice_number, candidate.invoice_number)
        and invoice.invoice_date == candidate.invoice_date
        and _same(invoice.seller_name, candidate.seller_name)
        and invoice.amount_with_tax == candidate.amount_with_tax
    ):
        return WEAK_RULE, Decimal("0.8500")
    if (
        not invoice.invoice_code
        and not candidate.invoice_code
        and _same(invoice.invoice_number, candidate.invoice_number)
        and invoice.invoice_date == candidate.invoice_date
        and invoice.amount_with_tax == candidate.amount_with_tax
    ):
        return ELECTRONIC_RULE, Decimal("0.7000")
    return None


def _same(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return False
    return left.strip() == right.strip()
