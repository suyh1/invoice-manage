import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import CredentialCipher, TENCENT_OCR_DEFAULTS
from app.domain.file.validators import validate_upload
from app.domain.ocr.client import TencentVatInvoiceOcrClient
from app.domain.ocr.errors import map_tencent_sdk_exception
from app.domain.ocr.models import OcrProviderConfig, QuotaSource


FIXTURES = Path(__file__).parent / "fixtures" / "ocr"


def make_provider() -> OcrProviderConfig:
    return OcrProviderConfig(
        provider="tencent",
        display_name="Tencent OCR",
        enabled=True,
        is_default=True,
        endpoint=TENCENT_OCR_DEFAULTS.endpoint,
        region=TENCENT_OCR_DEFAULTS.region,
        action=TENCENT_OCR_DEFAULTS.action,
        api_version=TENCENT_OCR_DEFAULTS.api_version,
        qps_limit=TENCENT_OCR_DEFAULTS.qps_limit,
        quota_source=QuotaSource.manual,
    )


def make_png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + (120).to_bytes(4, "big")
        + (80).to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )


def make_pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        + b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        + b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        + b"3 0 obj\n<< /Type /Page /Parent 2 0 R >>\nendobj\n"
        + b"%%EOF\n"
    )


def test_tencent_client_uses_image_base64_for_png(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    success_payload = json.loads((FIXTURES / "vat_invoice_success.json").read_text())

    class FakeCredential:
        def __init__(self, secret_id: str, secret_key: str) -> None:
            captured["credential"] = (secret_id, secret_key)

    class FakeHttpProfile:
        def __init__(self) -> None:
            self.endpoint = None

    class FakeClientProfile:
        def __init__(self) -> None:
            self.httpProfile = None

    class FakeRequest:
        def from_json_string(self, value: str) -> None:
            captured["request_payload"] = json.loads(value)

    class FakeResponse:
        def to_json_string(self) -> str:
            return json.dumps(success_payload)

    class FakeClient:
        def __init__(self, credential, region: str, profile) -> None:
            captured["region"] = region
            captured["endpoint"] = profile.httpProfile.endpoint

        def VatInvoiceOCR(self, request) -> FakeResponse:
            return FakeResponse()

    fake_modules = SimpleNamespace(
        Credential=FakeCredential,
        HttpProfile=FakeHttpProfile,
        ClientProfile=FakeClientProfile,
        OcrClient=FakeClient,
        VatInvoiceOCRRequest=FakeRequest,
        TencentCloudSDKException=Exception,
    )
    monkeypatch.setattr("app.domain.ocr.client.load_tencent_sdk", lambda: fake_modules)

    provider = make_provider()
    credentials = {"secret_id": "AKIDEXAMPLE", "secret_key": "SECRET"}
    upload = validate_upload("invoice.png", "image/png", make_png_bytes())

    result = TencentVatInvoiceOcrClient().recognize_file(provider, credentials, upload)

    assert result.request_id == "req-success-001"
    assert captured["credential"] == ("AKIDEXAMPLE", "SECRET")
    assert captured["region"] == TENCENT_OCR_DEFAULTS.region
    assert captured["endpoint"] == TENCENT_OCR_DEFAULTS.endpoint
    assert "ImageBase64" in captured["request_payload"]
    assert "IsPdf" not in captured["request_payload"]


def test_tencent_client_marks_pdf_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    success_payload = json.loads((FIXTURES / "vat_invoice_success.json").read_text())

    class FakeRequest:
        def from_json_string(self, value: str) -> None:
            captured["request_payload"] = json.loads(value)

    class FakeResponse:
        def to_json_string(self) -> str:
            return json.dumps(success_payload)

    fake_modules = SimpleNamespace(
        Credential=lambda secret_id, secret_key: None,
        HttpProfile=lambda: SimpleNamespace(endpoint=None),
        ClientProfile=lambda: SimpleNamespace(httpProfile=None),
        OcrClient=lambda credential, region, profile: SimpleNamespace(VatInvoiceOCR=lambda request: FakeResponse()),
        VatInvoiceOCRRequest=FakeRequest,
        TencentCloudSDKException=Exception,
    )
    monkeypatch.setattr("app.domain.ocr.client.load_tencent_sdk", lambda: fake_modules)

    provider = make_provider()
    upload = validate_upload("invoice.pdf", "application/pdf", make_pdf_bytes())

    TencentVatInvoiceOcrClient().recognize_file(provider, {"secret_id": "id", "secret_key": "key"}, upload)

    assert captured["request_payload"]["IsPdf"] is True
    assert captured["request_payload"]["PdfPageNumber"] == 1


def test_tencent_client_accepts_documented_http_response_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.loads((FIXTURES / "vat_invoice_success.json").read_text())

    class FakeRequest:
        def from_json_string(self, value: str) -> None:
            pass

    class FakeResponse:
        def to_json_string(self) -> str:
            return json.dumps({"Response": payload})

    fake_modules = SimpleNamespace(
        Credential=lambda secret_id, secret_key: None,
        HttpProfile=lambda: SimpleNamespace(endpoint=None),
        ClientProfile=lambda: SimpleNamespace(httpProfile=None),
        OcrClient=lambda credential, region, profile: SimpleNamespace(VatInvoiceOCR=lambda request: FakeResponse()),
        VatInvoiceOCRRequest=FakeRequest,
        TencentCloudSDKException=Exception,
    )
    monkeypatch.setattr("app.domain.ocr.client.load_tencent_sdk", lambda: fake_modules)

    upload = validate_upload("invoice.png", "image/png", make_png_bytes())
    result = TencentVatInvoiceOcrClient().recognize_file(
        make_provider(),
        {"secret_id": "id", "secret_key": "key"},
        upload,
    )

    assert result.raw_response == payload
    assert result.request_id == "req-success-001"


def test_tencent_exception_mapping_marks_rate_limit_retryable() -> None:
    exc = map_tencent_sdk_exception(
        SimpleNamespace(code="RequestLimitExceeded", message="too many requests", requestId="req-rate-limit-001")
    )

    assert exc.code == "OCR_PROVIDER_RATE_LIMITED"
    assert exc.retryable is True
    assert exc.provider == "tencent"
    assert exc.provider_code == "RequestLimitExceeded"
    assert exc.provider_request_id == "req-rate-limit-001"
