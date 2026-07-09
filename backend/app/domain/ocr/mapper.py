from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True)
class MappedOcrInvoice:
    invoice_fields: dict[str, Any]
    items: list[dict[str, Any]]
    extra_fields: dict[str, Any]
    raw_ocr_payload: dict[str, Any]
    normalized_payload: dict[str, Any]


class TencentVatInvoiceMapper:
    field_map = {
        "发票代码": ("invoice_code", "string"),
        "发票号码": ("invoice_number", "string"),
        "开票日期": ("invoice_date", "date"),
        "购买方名称": ("buyer_name", "string"),
        "购买方识别号": ("buyer_tax_id", "string"),
        "销售方名称": ("seller_name", "string"),
        "销售方识别号": ("seller_tax_id", "string"),
        "合计金额": ("amount_without_tax", "amount"),
        "合计税额": ("tax_amount", "amount"),
        "小写金额": ("amount_with_tax", "amount"),
        "价税合计": ("amount_with_tax", "amount"),
        "校验码": ("check_code", "string"),
        "发票类型": ("invoice_type", "string"),
    }

    item_field_map = {
        "Name": ("name", "string"),
        "Specification": ("specification", "string"),
        "Spec": ("specification", "string"),
        "Unit": ("unit", "string"),
        "Quantity": ("quantity", "quantity"),
        "UnitPrice": ("unit_price", "quantity"),
        "Amount": ("amount", "amount"),
        "TaxRate": ("tax_rate", "tax_rate"),
        "Tax": ("tax_amount", "amount"),
        "TaxAmount": ("tax_amount", "amount"),
    }

    def map(self, raw_response: dict[str, Any]) -> MappedOcrInvoice:
        invoice_fields: dict[str, Any] = {}
        unknown_infos: dict[str, Any] = {}
        unparsed_fields: dict[str, Any] = {}

        for info in raw_response.get("VatInvoiceInfos") or []:
            if not isinstance(info, dict):
                continue
            name = _clean_string(info.get("Name"))
            value = _clean_string(info.get("Value"))
            if not name or value is None:
                continue

            field_spec = self.field_map.get(name)
            if field_spec is None:
                unknown_infos[name] = value
                continue

            field_name, field_type = field_spec
            parsed = _parse_typed_value(value, field_type)
            if parsed is None:
                unparsed_fields[name] = value
                continue
            if field_name not in invoice_fields:
                invoice_fields[field_name] = parsed

        items = self._map_items(raw_response.get("Items") or [], unparsed_fields)
        extra_fields: dict[str, Any] = {}
        if unknown_infos:
            extra_fields["vat_invoice_infos"] = unknown_infos
        if unparsed_fields:
            extra_fields["unparsed_fields"] = unparsed_fields

        normalized_payload = {
            "invoice_fields": _json_safe(invoice_fields),
            "items": [_json_safe({key: value for key, value in item.items() if key != "raw_item_json"}) for item in items],
            "ocr_meta": {
                "request_id": raw_response.get("RequestId"),
                "pdf_page_size": raw_response.get("PdfPageSize"),
                "angle": raw_response.get("Angle"),
            },
            "extra_fields": _json_safe(extra_fields),
        }
        return MappedOcrInvoice(
            invoice_fields=invoice_fields,
            items=items,
            extra_fields=extra_fields,
            raw_ocr_payload=raw_response,
            normalized_payload=normalized_payload,
        )

    def _map_items(self, raw_items: list[Any], unparsed_fields: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for index, raw_item in enumerate(raw_items):
            if not isinstance(raw_item, dict):
                continue
            item: dict[str, Any] = {"raw_item_json": raw_item}
            for source_key, field_spec in self.item_field_map.items():
                if source_key not in raw_item:
                    continue
                value = _clean_string(raw_item.get(source_key))
                if value is None:
                    continue
                field_name, field_type = field_spec
                parsed = _parse_typed_value(value, field_type)
                if parsed is None:
                    unparsed_fields[f"Items[{index}].{source_key}"] = value
                    continue
                item[field_name] = parsed
            items.append(item)
        return items


def _parse_typed_value(value: str, field_type: str) -> Any:
    if field_type == "string":
        return _clean_string(value)
    if field_type == "date":
        return _parse_date(value)
    if field_type == "amount":
        return _parse_decimal(value, Decimal("0.01"))
    if field_type == "quantity":
        return _parse_decimal(value, Decimal("0.0001"))
    if field_type == "tax_rate":
        return _parse_tax_rate(value)
    raise ValueError(f"Unsupported OCR field type: {field_type}")


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _parse_date(value: str) -> date | None:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    match = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日", value)
    if match is None:
        return None
    year, month, day = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_decimal(value: str, quantum: Decimal) -> Decimal | None:
    normalized = value.replace(",", "").replace("，", "")
    match = re.search(r"-?\d+(?:\.\d+)?", normalized)
    if match is None:
        return None
    try:
        return Decimal(match.group(0)).quantize(quantum)
    except InvalidOperation:
        return None


def _parse_tax_rate(value: str) -> Decimal | None:
    decimal_value = _parse_decimal(value, Decimal("0.0001"))
    if decimal_value is None:
        return None
    if "%" in value or decimal_value > 1:
        decimal_value = decimal_value / Decimal("100")
    return decimal_value.quantize(Decimal("0.0001"))


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
