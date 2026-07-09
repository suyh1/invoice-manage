from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.domain.file.validators import ValidatedUpload
from app.domain.ocr.client import OcrRecognitionResult, ProviderCapability
from app.domain.ocr.models import OcrProviderConfig


class MockOcrClient:
    capability = ProviderCapability(
        provider="mock",
        display_name="Mock OCR",
        supported=True,
        supports_credential_test=False,
    )

    def __init__(self, fixture_path: Path | None = None) -> None:
        self.fixture_path = fixture_path

    def test_connection(self, provider_config: OcrProviderConfig, credential: dict[str, str] | None) -> dict[str, Any]:
        del provider_config, credential
        return {"ok": True, "message": "mock provider ready"}

    def recognize_file(
        self,
        provider_config: OcrProviderConfig,
        credential: dict[str, str],
        upload: ValidatedUpload,
    ) -> OcrRecognitionResult:
        del provider_config, credential, upload
        if self.fixture_path is not None:
            payload = json.loads(self.fixture_path.read_text())
        else:
            payload = {"VatInvoiceInfos": [], "Items": [], "PdfPageSize": 0, "Angle": 0, "RequestId": "mock-request"}
        return OcrRecognitionResult(raw_response=payload, request_id=payload.get("RequestId"))
