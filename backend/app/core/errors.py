from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        retryable: bool = False,
        *,
        provider: str | None = None,
        provider_code: str | None = None,
        provider_request_id: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.provider = provider
        self.provider_code = provider_code
        self.provider_request_id = provider_request_id
        super().__init__(message)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    error_payload = {
        "code": exc.code,
        "message": exc.message,
        "retryable": exc.retryable,
    }
    if exc.provider:
        error_payload["provider"] = exc.provider
    if exc.provider_code:
        error_payload["provider_code"] = exc.provider_code
    if exc.provider_request_id:
        error_payload["provider_request_id"] = exc.provider_request_id

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": error_payload,
            "request_id": request.headers.get("x-request-id", "local"),
        },
    )
