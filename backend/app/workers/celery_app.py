from __future__ import annotations

from celery import Celery

from app.core.config import get_settings
from app.db.base import import_all_models


settings = get_settings()
import_all_models()

celery_app = Celery(
    "invoice_ocr",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    accept_content=["json"],
    result_serializer="json",
    task_serializer="json",
    timezone="UTC",
    worker_concurrency=settings.worker_concurrency,
)
