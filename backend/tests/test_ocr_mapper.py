import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.domain.ocr.mapper import TencentVatInvoiceMapper


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ocr"


def test_tencent_mapper_maps_fixture_fields_and_items() -> None:
    payload = json.loads((FIXTURE_DIR / "vat_invoice_success.json").read_text())

    mapped = TencentVatInvoiceMapper().map(payload)

    assert mapped.raw_ocr_payload == payload
    assert mapped.invoice_fields["invoice_code"] == "144032216011"
    assert mapped.invoice_fields["invoice_number"] == "12876543"
    assert mapped.invoice_fields["invoice_date"] == date(2026, 7, 9)
    assert mapped.items == [
        {
            "name": "住宿服务",
            "specification": "标准间",
            "unit": "晚",
            "quantity": Decimal("1.0000"),
            "unit_price": Decimal("688.0000"),
            "amount": Decimal("688.00"),
            "tax_rate": Decimal("0.0600"),
            "tax_amount": Decimal("41.28"),
            "raw_item_json": payload["Items"][0],
        }
    ]
    assert mapped.normalized_payload["invoice_fields"]["invoice_date"] == "2026-07-09"
    assert mapped.normalized_payload["items"][0]["tax_rate"] == "0.0600"


def test_tencent_mapper_normalizes_amount_aliases_tax_rate_and_unrecognized_fields() -> None:
    payload = {
        "VatInvoiceInfos": [
            {"Name": "发票类型", "Value": " 增值税电子普通发票 "},
            {"Name": "购买方名称", "Value": "  星河科技有限公司 "},
            {"Name": "购买方识别号", "Value": " 91310000MA1K000001 "},
            {"Name": "销售方名称", "Value": " 上海云栖酒店 "},
            {"Name": "销售方识别号", "Value": "91310000MA1K000002"},
            {"Name": "开票日期", "Value": "2026年07月09日"},
            {"Name": "合计金额", "Value": "￥1,234.56"},
            {"Name": "合计税额", "Value": "（税额）￥74.07"},
            {"Name": "价税合计", "Value": "人民币（小写）￥1,308.63"},
            {"Name": "校验码", "Value": " 12345678901234567890 "},
            {"Name": "机器编号", "Value": "MACHINE-001"},
        ],
        "Items": [
            {
                "Name": "会议服务",
                "Specification": "",
                "Unit": "次",
                "Quantity": "2",
                "UnitPrice": "617.28",
                "Amount": "1,234.56",
                "TaxRate": "6%",
                "Tax": "74.07",
                "LineNo": "1",
            }
        ],
        "PdfPageSize": 0,
        "Angle": 90,
        "RequestId": "req-normalize-001",
    }

    mapped = TencentVatInvoiceMapper().map(payload)

    assert mapped.invoice_fields == {
        "invoice_type": "增值税电子普通发票",
        "buyer_name": "星河科技有限公司",
        "buyer_tax_id": "91310000MA1K000001",
        "seller_name": "上海云栖酒店",
        "seller_tax_id": "91310000MA1K000002",
        "invoice_date": date(2026, 7, 9),
        "amount_without_tax": Decimal("1234.56"),
        "tax_amount": Decimal("74.07"),
        "amount_with_tax": Decimal("1308.63"),
        "check_code": "12345678901234567890",
    }
    assert mapped.items[0]["tax_rate"] == Decimal("0.0600")
    assert mapped.items[0]["raw_item_json"] == payload["Items"][0]
    assert mapped.extra_fields["vat_invoice_infos"] == {"机器编号": "MACHINE-001"}
    assert mapped.normalized_payload["invoice_fields"]["amount_with_tax"] == "1308.63"


def test_tencent_mapper_keeps_unparsed_known_fields_in_extra_fields() -> None:
    payload = {
        "VatInvoiceInfos": [
            {"Name": "开票日期", "Value": "二零二六年七月九日"},
            {"Name": "合计金额", "Value": "人民币壹佰元整"},
            {"Name": "发票号码", "Value": " 00012345 "},
        ],
        "Items": [
            {
                "Name": "办公用品",
                "Quantity": "两件",
                "Amount": "not-an-amount",
                "TaxRate": "免税",
            }
        ],
        "RequestId": "req-unparsed-001",
    }

    mapped = TencentVatInvoiceMapper().map(payload)

    assert mapped.invoice_fields == {"invoice_number": "00012345"}
    assert mapped.items[0]["name"] == "办公用品"
    assert "quantity" not in mapped.items[0]
    assert "amount" not in mapped.items[0]
    assert "tax_rate" not in mapped.items[0]
    assert mapped.extra_fields["unparsed_fields"] == {
        "开票日期": "二零二六年七月九日",
        "合计金额": "人民币壹佰元整",
        "Items[0].Quantity": "两件",
        "Items[0].Amount": "not-an-amount",
        "Items[0].TaxRate": "免税",
    }
