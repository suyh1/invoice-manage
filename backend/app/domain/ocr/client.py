from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.errors import AppError
from app.domain.file.validators import ValidatedUpload
from app.domain.ocr.errors import map_tencent_sdk_exception
from app.domain.ocr.models import OcrProviderConfig


@dataclass(frozen=True)
class ProviderCapability:
    provider: str
    display_name: str
    supported: bool
    supports_credential_test: bool


@dataclass(frozen=True)
class OcrRecognitionResult:
    raw_response: dict[str, Any]
    request_id: str | None


class OcrProviderClient(Protocol):
    capability: ProviderCapability

    def test_connection(self, provider_config: OcrProviderConfig, credential: dict[str, str] | None) -> dict[str, Any]:
        ...

    def recognize_file(
        self,
        provider_config: OcrProviderConfig,
        credential: dict[str, str],
        upload: ValidatedUpload,
    ) -> OcrRecognitionResult:
        ...


def load_tencent_sdk():
    from tencentcloud.common.credential import Credential
    from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.ocr.v20181119 import models, ocr_client

    return type(
        "TencentSdk",
        (),
        {
            "Credential": Credential,
            "TencentCloudSDKException": TencentCloudSDKException,
            "ClientProfile": ClientProfile,
            "HttpProfile": HttpProfile,
            "OcrClient": ocr_client.OcrClient,
            "VatInvoiceOCRRequest": models.VatInvoiceOCRRequest,
        },
    )


class TencentVatInvoiceOcrClient:
    capability = ProviderCapability(
        provider="tencent",
        display_name="Tencent OCR",
        supported=True,
        supports_credential_test=True,
    )

    def test_connection(self, provider_config: OcrProviderConfig, credential: dict[str, str] | None) -> dict[str, Any]:
        if not credential or not credential.get("secret_id") or not credential.get("secret_key"):
            raise AppError("OCR_PROVIDER_AUTH_FAILED", "Tencent OCR credentials are required", status_code=400)
        self._build_client(provider_config, credential)
        return {"ok": True, "message": "client initialized"}

    def recognize_file(
        self,
        provider_config: OcrProviderConfig,
        credential: dict[str, str],
        upload: ValidatedUpload,
    ) -> OcrRecognitionResult:
        sdk = load_tencent_sdk()
        client = self._build_client(provider_config, credential, sdk=sdk)
        request = sdk.VatInvoiceOCRRequest()
        payload: dict[str, Any] = {"ImageBase64": base64.b64encode(upload.content).decode("ascii")}
        if upload.file_ext == "pdf":
            payload["IsPdf"] = True
            payload["PdfPageNumber"] = 1
        request.from_json_string(json.dumps(payload))

        try:
            response = client.VatInvoiceOCR(request)
        except Exception as exc:
            sdk_exception_type = getattr(sdk, "TencentCloudSDKException", Exception)
            if isinstance(exc, sdk_exception_type):
                raise map_tencent_sdk_exception(exc) from exc
            raise

        response_payload = json.loads(response.to_json_string())
        raw_response = response_payload.get("Response", response_payload)
        if not isinstance(raw_response, dict):
            raise AppError("OCR_PROVIDER_INVALID_RESPONSE", "Tencent OCR returned an invalid response", status_code=502)
        return OcrRecognitionResult(raw_response=raw_response, request_id=raw_response.get("RequestId"))

    def _build_client(self, provider_config: OcrProviderConfig, credential: dict[str, str], sdk=None):
        sdk = sdk or load_tencent_sdk()
        credential_obj = sdk.Credential(credential["secret_id"], credential["secret_key"])
        http_profile = sdk.HttpProfile()
        http_profile.endpoint = provider_config.endpoint
        client_profile = sdk.ClientProfile()
        client_profile.httpProfile = http_profile
        return sdk.OcrClient(credential_obj, provider_config.region, client_profile)
