from __future__ import annotations

from functools import lru_cache

from app.core.errors import AppError
from app.domain.ocr.client import ProviderCapability, TencentVatInvoiceOcrClient
from app.domain.ocr.mock_client import MockOcrClient


class OcrProviderRegistry:
    def __init__(self) -> None:
        self._clients = {
            "tencent": TencentVatInvoiceOcrClient(),
            "mock": MockOcrClient(),
        }
        self._capabilities = {
            "tencent": self._clients["tencent"].capability,
            "mock": self._clients["mock"].capability,
            "aliyun": ProviderCapability(
                provider="aliyun",
                display_name="Aliyun OCR",
                supported=False,
                supports_credential_test=False,
            ),
        }

    def list_capabilities(self) -> list[ProviderCapability]:
        return list(self._capabilities.values())

    def get_client(self, provider_name: str):
        if provider_name == "aliyun":
            raise AppError("OCR_PROVIDER_CONFIG_MISSING", "Aliyun OCR is modeled but not supported yet", status_code=400)
        client = self._clients.get(provider_name)
        if client is None:
            raise AppError("OCR_PROVIDER_CONFIG_MISSING", f"Unsupported OCR provider: {provider_name}", status_code=400)
        return client


@lru_cache
def get_registry() -> OcrProviderRegistry:
    return OcrProviderRegistry()
