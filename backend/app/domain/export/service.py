from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID
from xml.sax.saxutils import escape

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.errors import AppError
from app.domain.export.models import ExportFormat, ExportStatus, ExportTask
from app.domain.file.models import InvoiceDocument
from app.domain.invoice.models import Invoice, InvoiceStatus
from app.domain.user.models import User, UserRole


EXPORT_TTL_DAYS = 7
INVOICE_COLUMNS = [
    "id",
    "invoice_type",
    "invoice_code",
    "invoice_number",
    "invoice_date",
    "seller_name",
    "buyer_name",
    "amount_without_tax",
    "tax_amount",
    "amount_with_tax",
    "currency",
    "expense_scene",
    "project_id",
    "project_name",
    "project_visibility",
    "status",
    "document_filename",
]
ITEM_COLUMNS = ["invoice_id", "name", "specification", "unit", "quantity", "unit_price", "amount", "tax_rate", "tax_amount"]
OCR_COLUMNS = ["invoice_id", "job_id", "provider", "action", "status", "attempt_count", "request_id", "duration_ms"]


class ExportService:
    def create_task(self, db: Session, payload: dict[str, Any], current_user: User) -> ExportTask:
        export_format = ExportFormat(payload["format"])
        filters = dict(payload.get("filters") or {})
        filters["scope"] = payload.get("scope", "filtered_invoices")
        filters["include_items"] = bool(payload.get("include_items", True))
        filters["include_ocr_meta"] = bool(payload.get("include_ocr_meta", True))
        task = ExportTask(format=export_format, filters=filters, status=ExportStatus.queued, created_by=current_user.id)
        db.add(task)
        db.flush()
        return task

    def list_tasks(self, db: Session, current_user: User) -> list[ExportTask]:
        statement = select(ExportTask).order_by(ExportTask.created_at.desc(), ExportTask.id.desc())
        if current_user.role not in {UserRole.finance, UserRole.admin}:
            statement = statement.where(ExportTask.created_by == current_user.id)
        return list(db.scalars(statement))

    def get_task(self, db: Session, export_id: UUID, current_user: User) -> ExportTask:
        task = db.get(ExportTask, export_id)
        if task is None:
            raise AppError("EXPORT_NOT_FOUND", "Export task was not found", status_code=404)
        self.assert_export_access(task, current_user)
        return task

    def assert_export_access(self, task: ExportTask, current_user: User) -> None:
        if current_user.role in {UserRole.finance, UserRole.admin}:
            return
        if str(task.created_by) != str(current_user.id):
            raise AppError("AUTH_FORBIDDEN", "You do not have permission to access this export", status_code=403)

    def download_path(self, task: ExportTask, export_root: Path | None = None) -> Path:
        if task.status != ExportStatus.completed or not task.storage_key:
            raise AppError("EXPORT_NOT_READY", "Export file is not ready", status_code=409)
        if task.expires_at and _as_aware(task.expires_at) < datetime.now(UTC):
            raise AppError("EXPORT_EXPIRED", "Export file has expired", status_code=410)
        path = (export_root or get_settings().export_path) / task.storage_key
        if not path.exists():
            raise AppError("EXPORT_FILE_MISSING", "Export file is missing", status_code=404)
        return path


def run_export_task(task_id: UUID | str, *, db: Session, export_root: Path | None = None, now: datetime | None = None) -> ExportTask:
    now = now or datetime.now(UTC)
    task = db.get(ExportTask, task_id)
    if task is None:
        raise AppError("EXPORT_NOT_FOUND", "Export task was not found", status_code=404)
    task.status = ExportStatus.running
    task.error_message = None
    db.flush()
    try:
        export_root = export_root or get_settings().export_path
        export_root.mkdir(parents=True, exist_ok=True)
        invoices = _select_invoices(db, task.created_by_user, task.filters or {})
        payload = build_export_payload(task, invoices)
        content = render_export(task.format, payload)
        storage_key = f"exports/{task.id}.{task.format.value}"
        path = export_root / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

        task.storage_key = storage_key
        task.status = ExportStatus.completed
        task.expires_at = now + timedelta(days=EXPORT_TTL_DAYS)
        db.commit()
        return task
    except Exception as exc:
        task.status = ExportStatus.failed
        task.error_message = f"Export task failed ({exc.__class__.__name__})"
        db.commit()
        raise


def serialize_export_task(task: ExportTask) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "format": task.format.value,
        "filters": task.filters or {},
        "status": task.status.value,
        "storage_key": task.storage_key,
        "error_message": task.error_message,
        "created_by": str(task.created_by),
        "created_by_user": (
            {
                "id": str(task.created_by_user.id),
                "display_name": task.created_by_user.display_name,
                "email": task.created_by_user.email,
            }
            if task.created_by_user is not None
            else None
        ),
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "expires_at": task.expires_at.isoformat() if task.expires_at else None,
    }


def build_export_payload(task: ExportTask, invoices: list[Invoice]) -> dict[str, Any]:
    filters = task.filters or {}
    include_items = bool(filters.get("include_items", True))
    include_ocr_meta = bool(filters.get("include_ocr_meta", True))
    payload = {
        "invoices": [_invoice_row(invoice) for invoice in invoices],
        "items": [],
        "ocr_jobs": [],
        "export_metadata": {
            "id": str(task.id),
            "format": task.format.value,
            "filters": filters,
            "invoice_count": len(invoices),
        },
    }
    if include_items:
        payload["items"] = [_item_row(invoice, item) for invoice in invoices for item in invoice.items]
    if include_ocr_meta:
        payload["ocr_jobs"] = [_ocr_row(invoice) for invoice in invoices if invoice.latest_ocr_job is not None]
    return payload


def render_export(export_format: ExportFormat, payload: dict[str, Any]) -> bytes:
    if export_format == ExportFormat.json:
        return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    if export_format == ExportFormat.csv:
        return _render_csv(payload["invoices"], INVOICE_COLUMNS)
    if export_format == ExportFormat.xlsx:
        return _render_xlsx(payload)
    raise AppError("EXPORT_FORMAT_UNSUPPORTED", "Export format is not supported", status_code=400)


def _select_invoices(db: Session, user: User, filters: dict[str, Any]) -> list[Invoice]:
    statement = (
        select(Invoice)
        .join(Invoice.document)
        .options(
            selectinload(Invoice.document).selectinload(InvoiceDocument.project),
            selectinload(Invoice.items),
            selectinload(Invoice.latest_ocr_job),
        )
        .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
    )
    if user.role not in {UserRole.finance, UserRole.admin}:
        statement = statement.where(InvoiceDocument.uploaded_by == user.id)
    elif filters.get("uploaded_by"):
        statement = statement.where(InvoiceDocument.uploaded_by == UUID(str(filters["uploaded_by"])))

    if filters.get("project_id"):
        statement = statement.where(InvoiceDocument.project_id == UUID(str(filters["project_id"])))

    statuses = filters.get("status")
    if statuses:
        if isinstance(statuses, str):
            statuses = [statuses]
        statement = statement.where(Invoice.status.in_([InvoiceStatus(status) for status in statuses]))
    else:
        statement = statement.where(Invoice.status != InvoiceStatus.deleted)
    if filters.get("invoice_date_from"):
        statement = statement.where(Invoice.invoice_date >= datetime.fromisoformat(filters["invoice_date_from"]).date())
    if filters.get("invoice_date_to"):
        statement = statement.where(Invoice.invoice_date <= datetime.fromisoformat(filters["invoice_date_to"]).date())
    return list(db.scalars(statement))


def _invoice_row(invoice: Invoice) -> dict[str, str | None]:
    return {
        "id": str(invoice.id),
        "invoice_type": invoice.invoice_type,
        "invoice_code": invoice.invoice_code,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "seller_name": invoice.seller_name,
        "buyer_name": invoice.buyer_name,
        "amount_without_tax": _scalar(invoice.amount_without_tax),
        "tax_amount": _scalar(invoice.tax_amount),
        "amount_with_tax": _scalar(invoice.amount_with_tax),
        "currency": invoice.currency,
        "expense_scene": invoice.expense_scene,
        "project_id": str(invoice.document.project_id) if invoice.document and invoice.document.project_id else None,
        "project_name": invoice.document.project.name if invoice.document and invoice.document.project else None,
        "project_visibility": invoice.document.project.visibility.value if invoice.document and invoice.document.project else None,
        "status": invoice.status.value,
        "document_filename": invoice.document.original_filename if invoice.document else None,
    }


def _item_row(invoice: Invoice, item) -> dict[str, str | None]:
    return {
        "invoice_id": str(invoice.id),
        "name": item.name,
        "specification": item.specification,
        "unit": item.unit,
        "quantity": _scalar(item.quantity),
        "unit_price": _scalar(item.unit_price),
        "amount": _scalar(item.amount),
        "tax_rate": _scalar(item.tax_rate),
        "tax_amount": _scalar(item.tax_amount),
    }


def _ocr_row(invoice: Invoice) -> dict[str, str | int | None]:
    job = invoice.latest_ocr_job
    return {
        "invoice_id": str(invoice.id),
        "job_id": str(job.id),
        "provider": job.provider,
        "action": job.action,
        "status": job.status.value,
        "attempt_count": job.attempt_count,
        "request_id": job.request_id,
        "duration_ms": (job.raw_request_meta or {}).get("duration_ms"),
    }


def _render_csv(rows: list[dict[str, Any]], columns: list[str]) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue().encode("utf-8-sig")


def _render_xlsx(payload: dict[str, Any]) -> bytes:
    sheets = [
        ("Invoices", INVOICE_COLUMNS, payload["invoices"]),
        ("Items", ITEM_COLUMNS, payload["items"]),
        ("OCR Jobs", OCR_COLUMNS, payload["ocr_jobs"]),
        ("Export Metadata", ["key", "value"], _metadata_rows(payload["export_metadata"])),
    ]
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml(len(sheets)))
        archive.writestr("_rels/.rels", _root_rels_xml())
        archive.writestr("xl/workbook.xml", _workbook_xml([sheet[0] for sheet in sheets]))
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_rels_xml(len(sheets)))
        for index, (_, columns, rows) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(columns, rows))
    return output.getvalue()


def _metadata_rows(metadata: dict[str, Any]) -> list[dict[str, str]]:
    return [{"key": key, "value": json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)} for key, value in metadata.items()]


def _sheet_xml(columns: list[str], rows: list[dict[str, Any]]) -> str:
    sheet_rows = [_xlsx_row(columns, 1)]
    for row_index, row in enumerate(rows, start=2):
        sheet_rows.append(_xlsx_row([row.get(column) for column in columns], row_index))
    return '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{}</sheetData></worksheet>'.format(
        "".join(sheet_rows)
    )


def _xlsx_row(values: list[Any], row_index: int) -> str:
    cells = []
    for col_index, value in enumerate(values, start=1):
        ref = f"{_column_name(col_index)}{row_index}"
        cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape("" if value is None else str(value))}</t></is></c>')
    return f'<row r="{row_index}">{"".join(cells)}</row>'


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _content_types_xml(sheet_count: int) -> str:
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return f'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>{overrides}</Types>'


def _root_rels_xml() -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'


def _workbook_xml(sheet_names: list[str]) -> str:
    sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(sheet_names, start=1)
    )
    return f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{sheets}</sheets></workbook>'


def _workbook_rels_xml(sheet_count: int) -> str:
    relationships = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{relationships}</Relationships>'


def _scalar(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
