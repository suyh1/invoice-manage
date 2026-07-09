from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="Invoice OCR", version="0.1.0")
    application.add_exception_handler(AppError, app_error_handler)

    @application.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.exists():
        application.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")

    application.state.settings = settings
    return application


app = create_app()

