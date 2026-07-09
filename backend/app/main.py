from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes.admin_ocr import router as admin_ocr_router
from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router
from app.api.routes.exports import router as exports_router
from app.api.routes.invoices import duplicate_router, router as invoices_router
from app.api.routes.ocr_jobs import router as ocr_jobs_router
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="Invoice OCR", version="0.1.0")
    application.add_exception_handler(AppError, app_error_handler)
    application.include_router(admin_ocr_router)
    application.include_router(auth_router)
    application.include_router(documents_router)
    application.include_router(ocr_jobs_router)
    application.include_router(duplicate_router)
    application.include_router(invoices_router)
    application.include_router(exports_router)

    @application.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.exists():
        application.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")

    application.state.settings = settings
    return application


app = create_app()
