from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.domain.invoice.models import Invoice
from app.domain.invoice.service import InvoiceService
from app.domain.project.service import ProjectService
from app.domain.user.models import User


router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("")
def global_search(
    q: str = Query(min_length=2, max_length=120),
    limit: int = Query(default=6, ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="Search query must contain at least two characters")

    pattern = f"%{query}%"
    invoice_statement = (
        InvoiceService()
        .visible_invoice_statement(current_user)
        .where(
            or_(
                Invoice.invoice_number.ilike(pattern),
                Invoice.invoice_code.ilike(pattern),
                Invoice.seller_name.ilike(pattern),
                Invoice.buyer_name.ilike(pattern),
            )
        )
        .order_by(Invoice.created_at.desc(), Invoice.id.desc())
        .limit(limit)
    )
    invoices = list(db.scalars(invoice_statement))

    projects = [
        project
        for project in ProjectService().list_visible_projects(db, current_user)
        if query.casefold() in project.name.casefold()
        or (project.description is not None and query.casefold() in project.description.casefold())
    ][:limit]

    supplier_statement = (
        InvoiceService()
        .visible_invoice_statement(current_user)
        .with_only_columns(Invoice.seller_name, func.count(Invoice.id))
        .where(Invoice.seller_name.is_not(None), Invoice.seller_name != "", Invoice.seller_name.ilike(pattern))
        .group_by(Invoice.seller_name)
        .order_by(func.count(Invoice.id).desc(), Invoice.seller_name.asc())
        .limit(limit)
    )
    suppliers = db.execute(supplier_statement).all()

    return {
        "data": {
            "invoices": [
                {
                    "id": str(invoice.id),
                    "invoice_number": invoice.invoice_number,
                    "invoice_code": invoice.invoice_code,
                    "seller_name": invoice.seller_name,
                    "buyer_name": invoice.buyer_name,
                    "amount_with_tax": str(invoice.amount_with_tax) if invoice.amount_with_tax is not None else None,
                }
                for invoice in invoices
            ],
            "projects": [
                {"id": str(project.id), "name": project.name, "description": project.description}
                for project in projects
            ],
            "suppliers": [
                {"name": supplier_name, "invoice_count": invoice_count}
                for supplier_name, invoice_count in suppliers
            ],
        }
    }
