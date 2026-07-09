from __future__ import annotations

from types import SimpleNamespace

from app.core.errors import AppError


def map_tencent_sdk_exception(exc: object) -> AppError:
    code = str(getattr(exc, "code", "") or getattr(exc, "Code", "") or "UnknownError")
    message = str(getattr(exc, "message", "") or getattr(exc, "Message", "") or "Tencent OCR request failed")
    request_id = str(getattr(exc, "requestId", "") or getattr(exc, "RequestId", "") or "") or None

    lowered = code.lower()
    if "authfailure" in lowered or "signaturefailure" in lowered or "unauthorizedoperation" in lowered:
        return AppError(
            "OCR_PROVIDER_AUTH_FAILED",
            "Tencent OCR credentials are invalid",
            status_code=502,
            provider="tencent",
            provider_code=code,
            provider_request_id=request_id,
        )
    if "requestlimitexceeded" in lowered or "limitexceeded" in lowered:
        return AppError(
            "OCR_PROVIDER_RATE_LIMITED",
            "Tencent OCR rate limit was exceeded",
            status_code=503,
            retryable=True,
            provider="tencent",
            provider_code=code,
            provider_request_id=request_id,
        )
    if "resourceunavailable" in lowered or "arrears" in lowered:
        return AppError(
            "OCR_PROVIDER_IN_ARREARS",
            "Tencent OCR billing status is abnormal",
            status_code=502,
            provider="tencent",
            provider_code=code,
            provider_request_id=request_id,
        )
    if "quota" in lowered:
        return AppError(
            "OCR_PROVIDER_QUOTA_EXHAUSTED",
            "Tencent OCR quota or resource package is exhausted",
            status_code=502,
            provider="tencent",
            provider_code=code,
            provider_request_id=request_id,
        )
    if "timeout" in lowered or "internalerror" in lowered:
        return AppError(
            "OCR_PROVIDER_TIMEOUT",
            "Tencent OCR request timed out",
            status_code=503,
            retryable=True,
            provider="tencent",
            provider_code=code,
            provider_request_id=request_id,
        )
    if "nottextinimage" in lowered or "imagenotext" in lowered:
        return AppError(
            "OCR_RECOGNITION_EMPTY",
            "Tencent OCR did not detect text in the image",
            status_code=422,
            provider="tencent",
            provider_code=code,
            provider_request_id=request_id,
        )
    return AppError(
        "OCR_PROVIDER_UNKNOWN_ERROR",
        message,
        status_code=502,
        retryable=True,
        provider="tencent",
        provider_code=code,
        provider_request_id=request_id,
    )


def make_sdk_exception(code: str, message: str, request_id: str | None = None) -> object:
    return SimpleNamespace(code=code, message=message, requestId=request_id)
